include Makefile.mk

NAME=ec2-volume-manager
AWS_REGION=eu-central-1
S3_BUCKET_PREFIX=binxio-public
S3_BUCKET=$(S3_BUCKET_PREFIX)-$(AWS_REGION)

ALL_REGIONS=$(shell printf "import boto3\nprint('\\\n'.join(map(lambda r: r['RegionName'], boto3.client('ec2').describe_regions()['Regions'])))\n" | python | grep -v '^$(AWS_REGION)$$')

help:
	@echo 'make                 - builds a zip file to target/.'
	@echo 'make release         - builds a zip file and deploys it to s3.'
	@echo 'make clean           - the workspace.'
	@echo 'make test            - execute the tests, requires a working AWS connection.'
	@echo 'make deploy	    - lambda to bucket $(S3_BUCKET)'
	@echo 'make deploy-all-regions - lambda to all regions with bucket prefix $(S3_BUCKET_PREFIX)'
	@echo 'make deploy-lambda - deploys the manager.'
	@echo 'make delete-lambda - deletes the manager.'
	@echo 'make demo            - deploys the provider and the demo cloudformation stack.'
	@echo 'make delete-demo     - deletes the demo cloudformation stack.'

deploy: target/$(NAME)-$(VERSION).zip	## lambda zip file to bucket
	aws s3 --region $(AWS_REGION) \
		cp --acl \
		public-read target/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-$(VERSION).zip 
	aws s3 --region $(AWS_REGION) \
		cp --acl public-read \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-latest.zip 

deploy-all-regions: deploy		## lambda zip files to all buckets 
	@for REGION in $(ALL_REGIONS); do \
		echo "copying to region $$REGION.." ; \
		aws s3 --region $$REGION \
			cp --acl public-read \
			s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
		aws s3 --region $$REGION \
			cp  --acl public-read \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-latest.zip; \
	done

do-push: deploy

do-build: target/$(NAME)-$(VERSION).zip

target/$(NAME)-$(VERSION).zip: src/*/*.py requirements.txt Dockerfile.lambda
	mkdir -p target
	docker build --build-arg ZIPFILE=$(NAME)-$(VERSION).zip -t $(NAME)-lambda:$(VERSION) -f Dockerfile.lambda . && \
		ID=$$(docker create $(NAME)-lambda:$(VERSION) /bin/true) && \
		docker export $$ID | (cd target && tar -xvf - $(NAME)-$(VERSION).zip) && \
		docker rm -f $$ID && \
		chmod ugo+r target/$(NAME)-$(VERSION).zip

clean:
	rm -rf target
	find . -name \*.pyc | xargs rm 

Pipfile.lock: Pipfile requirements.txt test-requirements.txt
	pipenv install -r requirements.txt
	pipenv install -d -r test-requirements.txt

test: Pipfile.lock demo delete-lambda
	PYTHONPATH=$(PWD)/src pipenv run pytest tests/test*.py

fmt:
	black $(find src -name *.py) tests/*.py

deploy-lambda:
	aws cloudformation validate-template --template-body file://./cloudformation/ec2-volume-manager.yaml > /dev/null
	aws cloudformation deploy \
		--capabilities CAPABILITY_IAM \
		--stack-name $(NAME) \
		--template-file ./cloudformation/ec2-volume-manager.yaml \
		--parameter-overrides CFNCustomProviderZipFileName=lambdas/$(NAME)-$(VERSION).zip

delete-lambda:
	! aws cloudformation get-template --stack-name $(NAME) >/dev/null 2>&1 || \
		aws cloudformation delete-stack --stack-name $(NAME) && \
		 aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo: VPC_ID=$(shell aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs)
demo: SUBNET_IDS=$(shell aws ec2 describe-subnets --output text \
		--filters Name=vpc-id,Values=$(VPC_ID) Name=default-for-az,Values=true \
		--query 'join(`,`,sort_by(Subnets[?MapPublicIpOnLaunch], &AvailabilityZone)[*].SubnetId)')
demo: 
	aws cloudformation validate-template --template-body file://./cloudformation/demo-stack.yaml > /dev/null
	echo "deploy demo in default VPC $(VPC_ID), subnets $(SUBNET_IDS)" ; \
        ([[ -z $(VPC_ID) ]] || [[ -z $(SUBNET_IDS) ]] ) && \
                echo "Either there is no default VPC in your account or there are no subnets in the default VPC" && exit 1 ; \
	aws cloudformation deploy --stack-name $(NAME)-demo \
		--no-fail-on-empty-changeset \
		--capabilities CAPABILITY_IAM \
		--template ./cloudformation/demo-stack.yaml  \
		--parameter-overrides VPC=$(VPC_ID) Subnets=$(SUBNET_IDS)

delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

stateful-demo: VPC_ID=$(shell aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs)
stateful-demo: SUBNET_IDS=$(shell aws ec2 describe-subnets --output text \
		--filters Name=vpc-id,Values=$(VPC_ID) Name=default-for-az,Values=true \
		--query 'join(`,`,sort_by(Subnets[?MapPublicIpOnLaunch], &AvailabilityZone)[*].SubnetId)')
stateful-demo: 
	aws cloudformation validate-template --template-body file://./cloudformation/demo-stateful-stack.yaml > /dev/null
	echo "deploy demo in default VPC $(VPC_ID), subnets $(SUBNET_IDS)" ; \
        ([[ -z $(VPC_ID) ]] || [[ -z $(SUBNET_IDS) ]] ) && \
                echo "Either there is no default VPC in your account or there are no subnets in the default VPC" && exit 1 ; \
	aws cloudformation deploy --stack-name $(NAME)-stateful-demo \
		--no-fail-on-empty-changeset \
		--capabilities CAPABILITY_IAM \
		--template ./cloudformation/demo-stateful-stack.yaml  \
		--parameter-overrides VPC=$(VPC_ID) Subnets=$(SUBNET_IDS) Ami=/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-ebs

delete-stateful-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-stateful-demo
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-stateful-demo

