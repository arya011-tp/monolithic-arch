#!/usr/bin/env python3

import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    App, CfnOutput, Stack, Environment, Fn, Duration,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs
)

class BasePlatform(Construct):
    
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        environment_name = 'ecsworkshop'

        self.vpc = ec2.Vpc.from_lookup(
            self, "VPC",
            vpc_name='{}-base/BaseVPC'.format(environment_name)
        )

        self.ecs_cluster = ecs.Cluster.from_cluster_attributes(
            self, "ECSCluster",
            cluster_name=cdk.Fn.import_value('ECSClusterName'),
            security_groups=[],
            vpc=self.vpc
        )

        self.services_sec_grp = ec2.SecurityGroup.from_security_group_id(
            self, "ServicesSecGrp",
            security_group_id=cdk.Fn.import_value('ServicesSecGrp')
        )

class FrontendService(Stack):
    
    def __init__(self, scope: Stack, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.base_platform = BasePlatform(self, "BasePlatform")

        self.fargate_task_image = ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
            image=ecs.ContainerImage.from_registry("public.ecr.aws/aws-containers/ecsdemo-frontend"),
            container_port=3000,
            environment={
                "CRYSTAL_URL": "http://ecsdemo-crystal.service.local:3000/crystal",
                "NODEJS_URL": "http://ecsdemo-nodejs.service.local:3000",
                "REGION": os.getenv('AWS_DEFAULT_REGION')
            },
        )

        self.fargate_load_balanced_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "FrontendFargateLBService",
            service_name='ecsdemo-frontend',
            cluster=self.base_platform.ecs_cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            public_load_balancer=True,
            task_image_options=self.fargate_task_image
        )

        self.fargate_load_balanced_service.task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=['ec2:DescribeSubnets'],
                resources=['*']
            )
        )

        self.fargate_load_balanced_service.service.connections.allow_to(
            self.base_platform.services_sec_grp,
            port_range=ec2.Port(protocol=ec2.Protocol.TCP, string_representation="frontendtobackend", from_port=3000, to_port=3000)
        )

        self.autoscale = self.fargate_load_balanced_service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=10
        )

        self.autoscale.scale_on_cpu_utilization(
            "CPUAutoscaling",
            target_utilization_percent=50,
            scale_in_cooldown=Duration.seconds(30),
            scale_out_cooldown=Duration.seconds(30)
        )

        # Enable Service Autoscaling
        self.autoscale = self.fargate_load_balanced_service.service.auto_scale_task_count(
           min_capacity=1,
           max_capacity=10
        )
        
        self.autoscale.scale_on_cpu_utilization(
           "CPUAutoscaling",
           target_utilization_percent=50,
           scale_in_cooldown=Duration.seconds(30),
           scale_out_cooldown=Duration.seconds(30)
        )

_env = Environment(account=os.getenv('AWS_ACCOUNT_ID'), region=os.getenv('AWS_DEFAULT_REGION'))
environment = "ecsworkshop"
stack_name = "{}-frontend".format(environment)
app = App()
FrontendService(app, stack_name, env=_env)
app.synth()
