"""
AWS EC2 Volume manager

Manages volume attachments to EC2 instances

When a instances is stopped or terminated, the manager will remove all attachments are associated
with the instance.

When a instance is started, the manager will attach the volumes to the instance
"""
import logging
import os
from typing import List

import boto3
from botocore.exceptions import ClientError
from time import sleep

from .ec2_instance import EC2Instance, describe_instance, get_instances
from .volume import Volume, get_volumes

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
ec2 = boto3.client("ec2")


class Manager(object):
    def __init__(self, attachment_name: str):
        self.attachment_name: str = attachment_name
        self.volumes: List[Volume] = []
        self.instances: List[EC2Instance] = []

    def refresh(self):
        self.volumes = get_volumes(self.attachment_name)
        self.instances = get_instances(self.attachment_name)

    @property
    def running_instances(self) -> List[EC2Instance]:
        return list(filter(lambda i: i.state == "running", self.instances))

    @property
    def in_limbo_instances(self) -> List[EC2Instance]:
        return list(filter(lambda i: i.state not in ["stopped", "terminated", "running"], self.instances))

    @property
    def available_volumes(self) -> List[Volume]:
        return list(filter(lambda a: not a.attachments, self.volumes))

    @staticmethod
    def wait_for_state_attached(volumes: List[Volume]):
        states = []
        volume_ids = list(map(lambda v: v.volume_id, volumes))
        while len(volume_ids) != len(states):
            states = list(
                filter(
                    lambda v: v.attachment_state == "attached",
                    map(
                        lambda v: Volume(v),
                        ec2.describe_volumes(VolumeIds=volume_ids)["Volumes"],
                    ),
                )
            )
            logging.info(
                f"{len(states)} out of {len(volume_ids)} attached."
            )
            if len(volume_ids) != len(states):
                sleep(5)

    @staticmethod
    def wait_for_state_detached(volumes: List[Volume]):
        detached = []
        volume_ids = list(map(lambda v: v.volume_id, volumes))
        while len(volume_ids) != len(detached):
            detached = list(
                filter(
                    lambda v: not v.attachments,
                    map(
                        lambda v: Volume(v),
                        ec2.describe_volumes(VolumeIds=volume_ids)["Volumes"],
                    ),
                )
            )
            logging.info(
                f"{len(detached)} out of {len(volume_ids)} detached."
            )
            if len(volume_ids) != len(detached):
                sleep(5)

    def detach_attached_volumes(self, volumes: List[Volume]):
        """
        detach all `volumes`
        """
        for volume in volumes:
            if "attached" == volume.attachment_state:
                logging.info(f"detach volume '{volume.volume_id}' from '{volume.attached_to}'")
                ec2.detach_volume(VolumeId=volume.volume_id)
            elif "detaching" == volume.attachment_state:
                logging.debug(
                    f"volume '{volume.volume_id}' already detaching"
                )
            else:
                raise Exception(f"cannot detach volume '{volume.volume_id}' in state {volume.attachment_state}")
        self.wait_for_state_detached(volumes)
        self.volumes = get_volumes(self.attachment_name)

    def attach_volumes(self):
        """
        ensure all volumes are attached to the matching instance
        """
        self.refresh()

        if not self.volumes:
            logging.info(
                f"there are no volumes with tag ec2-volume-manager-attachment={self.attachment_name} to attach"
            )
            return

        log.info(f"attaching all volumes tagged with ec2-volume-manager-attachment={self.attachment_name}")
        if not self.running_instances:
            logging.info(
                f"no running instance with tag ec2-volume-manager-attachment={self.attachment_name} to attach to"
            )
            return

        if len(self.running_instances) > 1:
            logging.error(
                f"multiple instances with tag ec2-volume-manager-attachment={self.attachment_name}"
            )
            return

        if self.in_limbo_instances:
            logging.warning(
                f"cannot determine which instance to attach to: there are {len(self.in_limbo_instances)} instances with tag ec2-volume-manager-attachment={self.attachment_name} in flux"
            )
            return

        instance = self.running_instances[0]

        self.detach_attached_volumes(
            list(filter(lambda v : v.attached_to and instance.instance_id != v.attached_to, self.volumes))
        )

        volumes_to_attach = list(filter(lambda v : v.tags.get("device-name") and not v.attached_to, self.volumes))
        for volume in volumes_to_attach:
            if instance.instance_id != volume.attached_to:
                device_name = volume.tags.get("device-name")
                logging.info(
                    f"attaching volume {volume.volume_id} to {instance.instance_id} as device {device_name}"
                )
                ec2.attach_volume(
                    Device=device_name,
                    InstanceId=instance.instance_id,
                    VolumeId=volume.volume_id,
                )
        self.wait_for_state_attached(volumes_to_attach)

    def detach_volumes(self, instance_id: str):
        """
        detach all volumes from `instance_id`.
        """
        self.refresh()
        log.info(f"detaching all attached volumes from instance {instance_id} tagged with ec2-volume-manager-attachment={self.attachment_name}")
        volumes_to_detach = list(filter(lambda v: v.attachment_state == "attached" and instance_id == v.attached_to, self.volumes))
        for volume in volumes_to_detach:
            logging.info(f"detach volume '{volume.volume_id}' from '{instance_id}'")
            ec2.detach_volume(InstanceId=instance_id, VolumeId=volume.volume_id)
        self.wait_for_state_detached(volumes_to_detach)


def is_state_change_event(event):
    return event.get("source") == "aws.ec2" and event.get("detail-type") in [
        "EC2 Instance State-change Notification"
    ]


def is_attach_event(event):
    return (
        is_state_change_event(event) and event.get("detail").get("state") == "running"
    )


def is_detach_event(event):
    return is_state_change_event(event) and event.get("detail").get("state") in [
        "stopped",
        "terminated",
    ]


def is_timer(event) -> bool:
    return event.get("source") == "aws.events" and event.get("detail-type") in [
        "Scheduled Event"
    ]


def get_all_attachment_names() -> List[str]:
    result = []
    resourcetagging = boto3.client("resourcegroupstaggingapi")
    for values in resourcetagging.get_paginator("get_tag_values").paginate(
        Key="ec2-volume-manager-attachment"
    ):
        result.extend(values["TagValues"])
    return result


def handler(event: dict, context: dict):
    if is_attach_event(event) or is_detach_event(event):
        instance = describe_instance(event.get("detail").get("instance-id"))
        if not instance:
            return

        if not instance.attachment_name:
            log.info(
                f'ignoring instance "{instance.instance_id}" as it is not associated with a volume attachment'
            )
            return

        manager = Manager(instance.attachment_name)
        if is_detach_event(event):
            manager.detach_volumes(instance.instance_id)
        else:
            manager.attach_volumes()

    elif is_timer(event):
        log.info("consolidating")
        for attachment_name in get_all_attachment_names():
            manager = Manager(attachment_name)
            manager.attach_volumes()
    elif is_state_change_event(event):
        log.debug("ignored state change event %s", event.get("detail", {}).get("state"))
    else:
        log.error(
            "ignoring event %s from source %s",
            event.get("detail-type"),
            event.get("source"),
        )
