# -*- coding: utf-8 -*-
import datetime
import time
from json import JSONEncoder
from typing import Any, Callable, Dict, Optional

from chaoslib.types import Configuration, Secrets

from chaosaws import aws_client
from chaosaws.types import AWSResponse
from chaoslib import Secrets, ActivityFailed
from chaosaws.ec2.actions import terminate_instance
from logzero import logger

import random

__all__ = ["create_cluster", "delete_cluster", "terminate_random_nodes"]


def create_cluster(name: str, role_arn: str, vpc_config: Dict[str, Any],
                   version: str = None, configuration: Configuration = None,
                   secrets: Secrets = None) -> AWSResponse:
    """
    Create a new EKS cluster.
    """
    client = aws_client("eks", configuration, secrets)
    logger.debug("Creating EKS cluster: {}".format(name))
    return client.create_cluster(
        name=name, version=version, roleArn=role_arn,
        resourcesVpcConfig=vpc_config)


def delete_cluster(name: str = None, configuration: Configuration = None,
                   secrets: Secrets = None) -> AWSResponse:
    """
    Delete the given EKS cluster.
    """
    client = aws_client("eks", configuration, secrets)
    logger.debug("Deleting EKS cluster: {}".format(name))
    return client.delete_cluster(name=name)


def terminate_random_nodes(cluster_name: str,
                           aws_region: str,
                           node_count: int,
                           termination_timeout: int = 60,
                           secrets: Secrets = None):
    """
    Terminate random EKS nodes.

    The cluster_name must be specified so that a node instance (or multiple)
    can be terminated. termination_timeout controls how long a termination
    should take and is set to 60 by default; if the instance cannot be
    terminated within this timeout, the action will fail.
    """
    ec2_client = aws_client("ec2",
                            {"aws_region": aws_region},
                            secrets)
    ec2_describe_response = ec2_client.describe_instances(Filters=[
        {
            'Name': 'instance-state-name',
            'Values': ['running']
        },
        {
            'Name': 'network-interface.group-name',
            'Values': ["{}-workers".format(cluster_name)]
        }
    ])
    cluster_instances = []
    for reservation in ec2_describe_response['Reservations']:
        for instance in reservation['Instances']:
            cluster_instances.append(instance['InstanceId'])

    instances_to_terminate = random.sample(cluster_instances, node_count)
    for instanceId in instances_to_terminate:
        logger.info("Terminating {} instance".format(instanceId))
        terminate_instance(instance_id=instanceId,
                           configuration={"aws_region": aws_region})
        timeout = datetime.datetime.now() + datetime. \
            timedelta(0, termination_timeout)
        _wait_for(
            timeout,
            5,  # check every 5 seconds if instance was successfully terminated
            _instance_to_reach_terminated_state,
            "waiting for the instance to reach a terminated state",
            ec2_client,
            instanceId
        )


def _wait_for(
        timeout: datetime,
        interval: int,
        fn: Callable[..., bool],
        msg: str,
        *args: Any):
    logger.info(msg)
    while datetime.datetime.now() < timeout:
        if fn(*args):
            return
        time.sleep(interval)
    raise ActivityFailed("timed out {}".format(msg))


def _get_instance_from_instances(instances):
    if len(instances["Reservations"]) != 1:
        raise ActivityFailed(
            "unexpected number of reservations when listing "
            "ec2 instances: {}".format(len(instances["Reservations"]))
        )
    if len(instances["Reservations"][0]["Instances"]) != 1:
        raise ActivityFailed(
            "unexpected number of instances for filter: {}".format(
                len(instances["Reservations"]["Instances"]))
        )
    return instances["Reservations"][0]["Instances"][0]


def _instance_to_reach_terminated_state(ec2_client, instanceId) -> bool:
    instances = ec2_client.describe_instances(Filters=[{
        'Name': 'instance-id',
        'Values': [instanceId]
    }])
    updated_instance = _get_instance_from_instances(instances)
    return updated_instance["State"]["Name"] == "terminated"
