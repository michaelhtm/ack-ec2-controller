# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the SecurityGroup API.
"""

import logging
import resource
import time

import pytest
from acktest import tags
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import CRD_GROUP, CRD_VERSION, load_ec2_resource, service_marker
from e2e.bootstrap_resources import get_bootstrap_resources
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e.tests.helper import EC2Validator
from acktest.aws.identity import get_account_id

RESOURCE_PLURAL = "securitygroups"

CREATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10
MODIFY_WAIT_AFTER_SECONDS = 5

CREATE_CYCLIC_REF_AFTER_SECONDS = 60
DELETE_CYCLIC_REF_AFTER_SECONDS = 30


@pytest.fixture
def simple_security_group(request):
    resource_name = random_suffix_name("security-group-test", 24)
    resource_file = "security_group"
    test_vpc = get_bootstrap_resources().SharedTestVPC

    replacements = REPLACEMENT_VALUES.copy()
    replacements["SECURITY_GROUP_NAME"] = resource_name
    replacements["VPC_ID"] = test_vpc.vpc_id
    replacements["SECURITY_GROUP_DESCRIPTION"] = "TestSecurityGroup"

    marker = request.node.get_closest_marker("resource_data")
    if marker is not None:
        data = marker.args[0]
        if "resource_file" in data:
            resource_file = data["resource_file"]
            replacements.update(data)
        if "tag_key" in data:
            replacements["TAG_KEY"] = data["tag_key"]
        if "tag_value" in data:
            replacements["TAG_VALUE"] = data["tag_value"]

    # Load Security Group CR
    resource_data = load_ec2_resource(
        resource_file,
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    # Create k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP,
        CRD_VERSION,
        RESOURCE_PLURAL,
        resource_name,
        namespace="default",
    )

    k8s.create_custom_resource(ref, resource_data)
    time.sleep(CREATE_WAIT_AFTER_SECONDS)

    cr = k8s.wait_resource_consumed_by_controller(ref)
    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Try to delete, if doesn't already exist
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except:
        pass


@pytest.fixture
def security_group_with_vpc(request, simple_vpc):
    (_, vpc_cr) = simple_vpc
    vpc_id = vpc_cr["status"]["vpcID"]

    assert vpc_id is not None

    resource_name = random_suffix_name("security-group-vpc", 24)
    resource_file = "security_group"

    replacements = REPLACEMENT_VALUES.copy()
    replacements["SECURITY_GROUP_NAME"] = resource_name
    replacements["VPC_ID"] = vpc_id
    replacements["SECURITY_GROUP_DESCRIPTION"] = "TestSecurityGroup"

    marker = request.node.get_closest_marker("resource_data")
    if marker is not None:
        data = marker.args[0]
        if "resource_file" in data:
            resource_file = data["resource_file"]
            replacements.update(data)
        if "tag_key" in data:
            replacements["TAG_KEY"] = data["tag_key"]
        if "tag_value" in data:
            replacements["TAG_VALUE"] = data["tag_value"]

    # Load Security Group CR
    resource_data = load_ec2_resource(
        resource_file,
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    # Create k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP,
        CRD_VERSION,
        RESOURCE_PLURAL,
        resource_name,
        namespace="default",
    )

    k8s.create_custom_resource(ref, resource_data)
    time.sleep(CREATE_WAIT_AFTER_SECONDS)

    cr = k8s.wait_resource_consumed_by_controller(ref)
    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Try to delete, if doesn't already exist
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except:
        pass


def create_security_group_with_sg_ref(resource_name, reference_name):
    replacements = REPLACEMENT_VALUES.copy()
    replacements["VPC_ID"] = get_bootstrap_resources().SharedTestVPC.vpc_id
    replacements["SECURITY_GROUP_NAME"] = resource_name
    replacements["SECURITY_GROUP_REF_NAME"] = reference_name

    # Load Security Group CR
    resource_data = load_ec2_resource(
        "security_group_with_sg_ref",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    # Create k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP,
        CRD_VERSION,
        RESOURCE_PLURAL,
        resource_name,
        namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)

    return ref


@pytest.fixture
def security_groups_cyclic_ref():
    resource_name_1 = random_suffix_name("security-group-test", 24)
    resource_name_2 = random_suffix_name("security-group-test", 24)
    resource_name_3 = random_suffix_name("security-group-test", 24)

    ref_1 = create_security_group_with_sg_ref(resource_name_1, resource_name_2)
    ref_2 = create_security_group_with_sg_ref(resource_name_2, resource_name_3)
    ref_3 = create_security_group_with_sg_ref(resource_name_3, resource_name_1)

    time.sleep(CREATE_CYCLIC_REF_AFTER_SECONDS)

    cr_1 = k8s.wait_resource_consumed_by_controller(ref_1)
    cr_2 = k8s.wait_resource_consumed_by_controller(ref_2)
    cr_3 = k8s.wait_resource_consumed_by_controller(ref_3)
    assert cr_1 is not None
    assert cr_2 is not None
    assert cr_3 is not None

    yield [(ref_1, cr_1), (ref_2, cr_2), (ref_3, cr_3)]

    try:
        k8s.delete_custom_resource(ref, 3, 10)
        k8s.delete_custom_resource(ref, 3, 10)
        k8s.delete_custom_resource(ref, 3, 10)

        time.sleep(DELETE_CYCLIC_REF_AFTER_SECONDS)

        assert not k8s.get_resource_exists(ref_1)
        assert not k8s.get_resource_exists(ref_2)
        assert not k8s.get_resource_exists(ref_3)
    except:
        pass


@service_marker
@pytest.mark.canary
class TestSecurityGroup:
    def test_create_delete(self, ec2_client, simple_security_group):
        (ref, cr) = simple_security_group
        resource_id = cr["status"]["id"]

        # Check Security Group exists in AWS
        ec2_validator = EC2Validator(ec2_client)
        ec2_validator.assert_security_group(resource_id)

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted is True

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check Security Group no longer exists in AWS
        ec2_validator.assert_security_group(resource_id, exists=False)

    def test_create_with_vpc_add_egress_rule(self, ec2_client, security_group_with_vpc):
        (ref, cr) = security_group_with_vpc
        resource_id = cr["status"]["id"]

        # Check resource is synced successfully
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # Check Security Group exists in AWS
        ec2_validator = EC2Validator(ec2_client)
        ec2_validator.assert_security_group(resource_id)

        # Add a new Egress rule via patch
        new_egress_rule = {
            "ipProtocol": "-1",
            "ipRanges": [
                {
                    "cidrIP": "0.0.0.0/0",
                    "description": "Allow traffic from all IPs - test",
                }
            ],
        }
        patch = {"spec": {"egressRules": [new_egress_rule]}}
        _ = k8s.patch_custom_resource(ref, patch)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)

        # Check resource gets into synced state
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # assert patched state
        cr = k8s.get_resource(ref)
        assert len(cr["status"]["rules"]) == 1

        # Check egress rule exists
        sg_group = ec2_validator.get_security_group(resource_id)
        assert len(sg_group["IpPermissions"]) == 0
        assert len(sg_group["IpPermissionsEgress"]) == 1

        # Check egress rule data
        assert sg_group["IpPermissionsEgress"][0]["IpProtocol"] == "-1"
        assert len(sg_group["IpPermissionsEgress"][0]["IpRanges"]) == 1
        ip_range = sg_group["IpPermissionsEgress"][0]["IpRanges"][0]
        assert ip_range["CidrIp"] == "0.0.0.0/0"
        assert ip_range["Description"] == "Allow traffic from all IPs - test"

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted is True

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check Security Group no longer exists in AWS
        # Deleting Security Group will also delete rules
        ec2_validator.assert_security_group(resource_id, exists=False)

    @pytest.mark.resource_data(
        {
            "resource_file": "security_group_rule",
            "IP_PROTOCOL": "tcp",
            "FROM_PORT": "80",
            "TO_PORT": "80",
            "CIDR_IP": "172.31.0.0/16",
            "DESCRIPTION_INGRESS": "test ingress rule",
        }
    )
    def test_rules_create_update_delete(self, ec2_client, simple_security_group):
        (ref, cr) = simple_security_group
        resource_id = cr["status"]["id"]

        # Check resource is synced successfully
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # Check Security Group exists in AWS
        ec2_validator = EC2Validator(ec2_client)
        ec2_validator.assert_security_group(resource_id)

        # Hook code should update Spec rules using data from ReadOne resp
        assert len(cr["spec"]["ingressRules"]) == 1

        # Check ingress rule added
        assert len(cr["status"]["rules"]) == 1
        sg_group = ec2_validator.get_security_group(resource_id)
        assert len(sg_group["IpPermissions"]) == 1

        # Add Egress rule via patch
        new_egress_rule = {
            "ipProtocol": "tcp",
            "fromPort": 25,
            "toPort": 25,
            "ipRanges": [{"cidrIP": "172.31.0.0/16", "description": "test egress"}],
        }
        # Add Egress rule via patch
        new_egress_rule_with_sg_pair = {
            "ipProtocol": "tcp",
            "fromPort": 40,
            "toPort": 40,
            "ipRanges": [{"cidrIP": "172.31.0.0/12", "description": "test egress"}],
            "userIDGroupPairs": [
                {
                    "description": "test userIDGroupPairs",
                    "userID": str(get_account_id()),
                }
            ],
        }
        patch = {
            "spec": {"egressRules": [new_egress_rule, new_egress_rule_with_sg_pair]}
        }
        _ = k8s.patch_custom_resource(ref, patch)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)

        # Check resource gets into synced state
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # Check ingress and egress rules exist
        sg_group = ec2_validator.get_security_group(resource_id)
        assert len(sg_group["IpPermissions"]) == 1
        assert len(sg_group["IpPermissionsEgress"]) == 2

        # Check egress rule data
        assert sg_group["IpPermissionsEgress"][0]["IpProtocol"] == "tcp"
        assert sg_group["IpPermissionsEgress"][0]["FromPort"] == 25
        assert sg_group["IpPermissionsEgress"][0]["ToPort"] == 25
        assert (
            sg_group["IpPermissionsEgress"][0]["IpRanges"][0]["Description"]
            == "test egress"
        )

        assert sg_group["IpPermissionsEgress"][1]["IpProtocol"] == "tcp"
        assert sg_group["IpPermissionsEgress"][1]["FromPort"] == 40
        assert sg_group["IpPermissionsEgress"][1]["ToPort"] == 40
        assert (
            sg_group["IpPermissionsEgress"][1]["IpRanges"][0]["Description"]
            == "test egress"
        )
        assert len(sg_group["IpPermissionsEgress"][1]["UserIdGroupPairs"]) == 1
        assert (
            sg_group["IpPermissionsEgress"][1]["UserIdGroupPairs"][0]["Description"]
            == "test userIDGroupPairs"
        )
        assert (
            sg_group["IpPermissionsEgress"][1]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id
        )

        # Remove Ingress rule
        patch = {"spec": {"ingressRules": []}}
        _ = k8s.patch_custom_resource(ref, patch)
        time.sleep(CREATE_WAIT_AFTER_SECONDS)

        # assert patched state
        cr = k8s.get_resource(ref)
        assert len(cr["status"]["rules"]) == 3

        # Check ingress rule removed; egress rule remains
        sg_group = ec2_validator.get_security_group(resource_id)
        assert len(sg_group["IpPermissions"]) == 0
        assert len(sg_group["IpPermissionsEgress"]) == 2

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted is True

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check Security Group no longer exists in AWS
        # Deleting Security Group will also delete rules
        ec2_validator.assert_security_group(resource_id, exists=False)

    @pytest.mark.resource_data(
        {"tag_key": "initialtagkey", "tag_value": "initialtagvalue"}
    )
    def test_crud_tags(self, ec2_client, simple_security_group):
        (ref, cr) = simple_security_group

        resource = k8s.get_resource(ref)
        resource_id = cr["status"]["id"]

        time.sleep(CREATE_WAIT_AFTER_SECONDS)

        # Check SecurityGroup exists in AWS
        ec2_validator = EC2Validator(ec2_client)
        ec2_validator.assert_security_group(resource_id)

        # Check system and user tags exist for security group resource
        security_group = ec2_validator.get_security_group(resource_id)
        user_tags = {"initialtagkey": "initialtagvalue"}
        tags.assert_ack_system_tags(
            tags=security_group["Tags"],
        )
        tags.assert_equal_without_ack_tags(
            expected=user_tags,
            actual=security_group["Tags"],
        )

        # Only user tags should be present in Spec
        assert len(resource["spec"]["tags"]) == 1
        assert resource["spec"]["tags"][0]["key"] == "initialtagkey"
        assert resource["spec"]["tags"][0]["value"] == "initialtagvalue"

        # Update tags
        update_tags = [
            {
                "key": "updatedtagkey",
                "value": "updatedtagvalue",
            }
        ]

        # Patch the SecurityGroup, updating the tags with new pair
        updates = {
            "spec": {"tags": update_tags},
        }

        k8s.patch_custom_resource(ref, updates)
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        # Check resource synced successfully
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # Check for updated user tags; system tags should persist
        security_group = ec2_validator.get_security_group(resource_id)
        updated_tags = {"updatedtagkey": "updatedtagvalue"}
        tags.assert_ack_system_tags(
            tags=security_group["Tags"],
        )
        tags.assert_equal_without_ack_tags(
            expected=updated_tags,
            actual=security_group["Tags"],
        )

        # Only user tags should be present in Spec
        resource = k8s.get_resource(ref)
        assert len(resource["spec"]["tags"]) == 1
        assert resource["spec"]["tags"][0]["key"] == "updatedtagkey"
        assert resource["spec"]["tags"][0]["value"] == "updatedtagvalue"

        # Patch the SecurityGroup resource, deleting the tags
        updates = {
            "spec": {"tags": []},
        }

        k8s.patch_custom_resource(ref, updates)
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        # Check resource synced successfully
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # Check for removed user tags; system tags should persist
        security_group = ec2_validator.get_security_group(resource_id)
        tags.assert_ack_system_tags(
            tags=security_group["Tags"],
        )
        tags.assert_equal_without_ack_tags(
            expected=[],
            actual=security_group["Tags"],
        )

        # Check user tags are removed from Spec
        resource = k8s.get_resource(ref)
        assert len(resource["spec"]["tags"]) == 0

        # Delete k8s resource
        _, deleted = k8s.delete_custom_resource(ref)
        assert deleted is True

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check SecurityGroup no longer exists in AWS
        ec2_validator.assert_security_group(resource_id, exists=False)

    def test_cyclic_ref(self, ec2_client, security_groups_cyclic_ref):
        sgs = security_groups_cyclic_ref
        (ref_1, cr_1) = sgs[0]
        (ref_2, cr_2) = sgs[1]
        (ref_3, cr_3) = sgs[2]

        # Check Security Groups exists in AWS
        resource_id_1 = cr_1["status"]["id"]
        resource_id_2 = cr_2["status"]["id"]
        resource_id_3 = cr_3["status"]["id"]

        ec2_validator = EC2Validator(ec2_client)
        ec2_validator.assert_security_group(resource_id_1)
        ec2_validator.assert_security_group(resource_id_2)
        ec2_validator.assert_security_group(resource_id_3)

        # Check resources are synced successfully
        assert k8s.wait_on_condition(
            ref_1, "ACK.ResourceSynced", "True", wait_periods=5
        )
        assert k8s.wait_on_condition(
            ref_2, "ACK.ResourceSynced", "True", wait_periods=5
        )
        assert k8s.wait_on_condition(
            ref_3, "ACK.ResourceSynced", "True", wait_periods=5
        )

        sg_group_1 = ec2_validator.get_security_group(resource_id_1)
        sg_group_2 = ec2_validator.get_security_group(resource_id_2)
        sg_group_3 = ec2_validator.get_security_group(resource_id_3)

        # Check ingress rules exist
        assert len(sg_group_1["IpPermissions"]) == 1
        assert len(sg_group_2["IpPermissions"]) == 1
        assert len(sg_group_3["IpPermissions"]) == 1

        # Check egress rules exist
        assert len(sg_group_1["IpPermissionsEgress"]) == 1
        assert len(sg_group_2["IpPermissionsEgress"]) == 1
        assert len(sg_group_3["IpPermissionsEgress"]) == 1

        # Check ingress rules cyclic data
        assert (
            sg_group_1["IpPermissions"][0]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id_2
        )
        assert (
            sg_group_2["IpPermissions"][0]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id_3
        )
        assert (
            sg_group_3["IpPermissions"][0]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id_1
        )

        # Check egress rules cyclic data
        assert (
            sg_group_1["IpPermissionsEgress"][0]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id_2
        )
        assert (
            sg_group_2["IpPermissionsEgress"][0]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id_3
        )
        assert (
            sg_group_3["IpPermissionsEgress"][0]["UserIdGroupPairs"][0]["GroupId"]
            == resource_id_1
        )

        # Delete k8s resources
        k8s.delete_custom_resource(ref_1)
        k8s.delete_custom_resource(ref_2)
        k8s.delete_custom_resource(ref_3)

        time.sleep(DELETE_CYCLIC_REF_AFTER_SECONDS)

        assert not k8s.get_resource_exists(ref_1)
        assert not k8s.get_resource_exists(ref_2)
        assert not k8s.get_resource_exists(ref_3)

        # Check Security Group no longer exists in AWS
        ec2_validator.assert_security_group(resource_id_1, exists=False)
        ec2_validator.assert_security_group(resource_id_2, exists=False)
        ec2_validator.assert_security_group(resource_id_3, exists=False)
