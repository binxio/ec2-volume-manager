import copy
import boto3
from typing import List
from ec2_volume_manager import (
    handler,
    Manager,
    Volume,
    get_instances,
    get_volumes
)

event = {
    "id": "7bf73129-1428-4cd3-a780-95db273d1602",
    "detail-type": "EC2 Instance State-change Notification",
    "source": "aws.ec2",
    "account": "123456789012",
    "time": "2015-11-11T21:29:54Z",
    "region": "us-east-1",
    "resources": ["arn:aws:ec2:us-east-1:123456789012:instance/i-abcd1111"],
    "detail": {"instance-id": "i-abcd1111", "state": "running"},
}


ec2 = boto3.client("ec2")


def get_volumes() -> (List[Volume], List[Volume], List[Volume]):
    response = ec2.describe_volumes(
        Filters=[
            {"Name": "tag:ec2-volume-manager-attachment", "Values": ["stateful-instance-1"]},
        ]
    )
    volumes = list(map(lambda v: Volume(v), response["Volumes"]))
    assert len(volumes) == 2
    return (
        volumes,
        list(filter(lambda v: v.attachments, volumes)),
        list(filter(lambda v: not v.attachments, volumes)),
    )


def detach_all():
    _, volumes, _ = get_volumes()
    for v in volumes:
        ec2.detach_volume(VolumeId=v.volume_id)
    Manager.wait_for_state_detached(volumes)

    all, attached, unattached = get_volumes()
    assert len(attached) == 0
    assert len(unattached) == 2

def test_attach_and_detach_volumes():
    detach_all()
    manager = Manager('stateful-instance-1')
    manager.attach_volumes()

    all, attached, unattached = get_volumes()
    assert len(attached) == 2
    assert len(unattached) == 0

    manager = Manager('stateful-instance-1')
    manager.refresh()
    instance_id = manager.instances[0].instance_id
    manager.detach_volumes(instance_id)
    all, attached, unattached = get_volumes()
    assert len(attached) == 0
    assert len(unattached) == 2


