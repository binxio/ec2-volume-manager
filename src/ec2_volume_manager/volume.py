import logging
import os
from typing import List, Optional

import boto3

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
ec2 = boto3.client("ec2")


class Volume(dict):
    def __init__(self, instance: dict):
        super(Volume,self).__init__()
        self.update(instance)
        self.attachments = [Attachment(a) for a in self.get("Attachments",[])]
        if len(self.attachments) > 1:
            ## the API does support this, but the documentation says that EBS cannot be mounted on multiple instances
            raise Exception(f"Manager does not support volumes with multiple attachments ({self.volume_id}).")

    @property
    def volume_id(self) -> str:
        return self.get("VolumeId")

    @property
    def attached_to(self) -> str:
        return self.attachments[0].instance_id if self.attachments else None

    @property
    def attachment_state(self) -> str:
        return self.attachments[0].state if self.attachments else None

    @property
    def attachment_name(self) -> Optional[str]:
        return self.tags.get("ec2-volume-manager-attachment")

    @property
    def tags(self) -> dict:
        return {t["Key"]: t["Value"] for t in self["Tags"]}

    def __key(self):
        return self.volume_id

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __str__(self):
        return str(self.__key())

class Attachment(dict):
    def __init__(self, attachment: dict):
        super(Attachment,self).__init__()
        self.update(attachment)

    @property
    def instance_id(self) -> Optional[str]:
        return self.get("InstanceId")

    @property
    def volume_id(self) -> Optional[str]:
        return self.get("VolumeId")

    @property
    def device(self) -> Optional[str]:
        return self.get("Device")

    @property
    def state(self) -> Optional[str]:
        return self.get("State")



def get_volumes(attachment_name: str) -> List[Volume]:
    response = ec2.describe_volumes(
        Filters=[
            {"Name": "tag:ec2-volume-manager-attachment", "Values": [attachment_name]},
        ]
    )
    return [Volume(a) for a in response["Volumes"]]
