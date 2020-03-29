# AWS EC2 Volume manager
The ec2-volume-manager, manages the attachment of volumes to ec2 instances.  When the instance is stopped or terminated, the volume attachments are removed. 
  When a new instance is started, an volume is attached to it.  The goal of the volume manager is to be able to update the AMI of a stateful server, 
  without loosing the data by defining a autoscaling group of instance size 1 and perform a rolling update.

## How does it work?
The manager will listen to all EC2 instance state change notifications. When an instance with the tag `ec2-volume-manager-attachments` 
  reaches the state running, it will attach all volumes with the same tag and value.  The volumes will need to have a tag `device-name`
  which is used in the volume attachment.

## How do I use it?
You can start using the EC2 volume manager, in three simple steps:

1. deploy the ec2-volume-manager
2. create and tag the volumes
3. create an auto scaling group size 1, propagating the tag

## deploy the ec2-volume-manager
To deploy the provider, type:

```sh
git clone https://github.com/binxio/ec2-volume-manager.git
cd ec2-ec2-volume-manager
aws cloudformation deploy \
        --capabilities CAPABILITY_IAM \
        --stack-name ec2-volume-manager \
        --template ./cloudformation/ec2-volume-manager.yaml
```
## Create one or more volumes to attach
Create the volumes to attach and tag them with an `ec2-volume-manager-attachment` value:
```
  Disk1:
    Type: AWS::EC2::Volume
    Properties:
      AvailabilityZone: !Sub '${AWS::Region}a'
      Size: 8
      Tags:
        - Key: ec2-volume-manager-attachment'
          Value: stateful-instance-1
        - Key: device-name
          Value: xvdf

  Disk2:
    Type: AWS::EC2::Volume
    Properties:
      AvailabilityZone: !Sub '${AWS::Region}b'
      Size: 8
      Tags:
        - Key: ec2-volume-manager-attachment
          Value: stateful-instance-1
        - Key: device-name
          Value: xvdg

```

## Create an auto scaling group
Create an auto scaling group and apply the tag `ec2-volume-manager-attachment` to the instances:
```
  AutoScalingGroup:
    Type: AWS::AutoScaling::AutoScalingGroup
    Properties:
      MinSize: '0'
      MaxSize: '1'
      DesiredCapacity: '1'
      Tags:
        - Key: ec2-volume-manager-attachment
          Value: stateful-instance-1
          PropagateAtLaunch: true
    UpdatePolicy:
      AutoScalingRollingUpdate:
        MinInstancesInService: 0
        MaxBatchSize: 1
        WaitOnResourceSignals: true
```
That is all. If you want to see it all in action, deploy the demo.

Note that the instance should wait in the boot script, until all volumes have been attached before proceeding
with the boot sequence and report succesful completion using cfn-signal.

## Deploy the demo
In order to deploy the demo, type:

```sh
export VPC_ID=$(aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs)
export SUBNET_IDS=$(aws ec2 describe-subnets --output text \
                --filters Name=vpc-id,Values=$(VPC_ID) \
				          Name=default-for-az,Values=true \
                --query 'join(`,`,sort_by(Subnets[?MapPublicIpOnLaunch], &AvailabilityZone)[*].SubnetId)')
aws cloudformation deploy \
        --capabilities CAPABILITY_NAMED_IAM \
        --stack-name ec2-volume-manager-demo \
        --template ./cloudformation/demo-stack.yaml \
        --parameter-overrides VPC=$VPC_ID Subnets=$SUBNET_IDS
```


Read the blog too: [How to update an ec2 instance with volume attachments using CloudFormation](https://binx.io/blog/2020/03/29/how-to-update-the-boot-image-of-a-stateful-machine-using-cloudformation/)
