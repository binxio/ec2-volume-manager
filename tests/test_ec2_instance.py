from ec2_volume_manager.ec2_instance import EC2Instance


def test_ec2_instance_get_tags():
    data = {
        "AmiLaunchIndex": 0,
        "ImageId": "ami-0caa0ee1474fb9a30",
        "InstanceId": "i-055ca20559826a323",
        "InstanceType": "a1.medium",
        "KeyName": "mark",
        "LaunchTime": "2020-07-04T19:04:05+00:00",
        "Monitoring": {"State": "disabled"},
        "Placement": {
            "AvailabilityZone": "eu-central-1a",
            "GroupName": "",
            "Tenancy": "default",
        },
        "PrivateDnsName": "ip-172-31-100-247.eu-central-1.compute.internal",
        "PrivateIpAddress": "172.31.100.247",
        "ProductCodes": [],
        "PublicDnsName": "",
        "State": {"Code": 80, "Name": "stopped"},
        "StateTransitionReason": "User initiated (2020-07-08 18:53:58 GMT)",
        "SubnetId": "subnet-0c65e4d84b1604b59",
        "VpcId": "vpc-0c88bfb65b4198839",
        "Architecture": "arm64",
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "AttachTime": "2020-07-04T19:04:05+00:00",
                    "DeleteOnTermination": True,
                    "Status": "attached",
                    "VolumeId": "vol-0eee1a4888b1716a9",
                },
            }
        ],
        "ClientToken": "",
        "EbsOptimized": True,
        "EnaSupport": True,
        "Hypervisor": "xen",
        "IamInstanceProfile": {
            "Arn": "arn:aws:iam::123456789012:instance-profile/ssm-managed-instance",
            "Id": "AIPAWOZQJPZZSMUE2QQNX",
        },
        "NetworkInterfaces": [
            {
                "Attachment": {
                    "AttachTime": "2020-07-04T19:04:05+00:00",
                    "AttachmentId": "eni-attach-0d38f62d80bada54d",
                    "DeleteOnTermination": True,
                    "DeviceIndex": 0,
                    "Status": "attached",
                },
                "Description": "Primary network interface",
                "Groups": [
                    {"GroupName": "launch-wizard-2", "GroupId": "sg-09d0bcd6a5daf28b0"}
                ],
                "Ipv6Addresses": [],
                "MacAddress": "02:ab:32:b1:bb:0a",
                "NetworkInterfaceId": "eni-00dc7f84506b95b6f",
                "OwnerId": "123456789012",
                "PrivateDnsName": "ip-172-31-100-247.eu-central-1.compute.internal",
                "PrivateIpAddress": "172.31.100.247",
                "PrivateIpAddresses": [
                    {
                        "Primary": True,
                        "PrivateDnsName": "ip-172-31-100-247.eu-central-1.compute.internal",
                        "PrivateIpAddress": "172.31.100.247",
                    }
                ],
                "SourceDestCheck": True,
                "Status": "in-use",
                "SubnetId": "subnet-0c65e4d84b1604b59",
                "VpcId": "vpc-0c88bfb65b4198839",
                "InterfaceType": "interface",
            }
        ],
        "RootDeviceName": "/dev/xvda",
        "RootDeviceType": "ebs",
        "SecurityGroups": [
            {"GroupName": "launch-wizard-2", "GroupId": "sg-09d0bcd6a5daf28b0"}
        ],
        "SourceDestCheck": True,
        "StateReason": {
            "Code": "Client.UserInitiatedShutdown",
            "Message": "Client.UserInitiatedShutdown: User initiated shutdown",
        },
        "VirtualizationType": "hvm",
        "CpuOptions": {"CoreCount": 1, "ThreadsPerCore": 1},
        "CapacityReservationSpecification": {"CapacityReservationPreference": "open"},
        "HibernationOptions": {"Configured": False},
        "MetadataOptions": {
            "State": "applied",
            "HttpTokens": "optional",
            "HttpPutResponseHopLimit": 1,
            "HttpEndpoint": "enabled",
        },
    }

    instance = EC2Instance(data)
    assert instance.instance_id == "i-055ca20559826a323"
    assert instance.tags == {}
    assert instance.state == "stopped"
    assert instance.attachment_name == None

    data["Tags"] = [{"Key": "ec2-volume-manager-attachment", "Value": "disk1"}]
    instance = EC2Instance(data)
    assert instance.instance_id == "i-055ca20559826a323"
    assert instance.tags == {"ec2-volume-manager-attachment": "disk1"}
    assert instance.state == "stopped"
    assert instance.attachment_name == "disk1"
