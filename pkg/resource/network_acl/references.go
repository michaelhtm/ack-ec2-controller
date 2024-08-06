// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
// express or implied. See the License for the specific language governing
// permissions and limitations under the License.

// Code generated by ack-generate. DO NOT EDIT.

package network_acl

import (
	"context"
	"fmt"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"

	ackv1alpha1 "github.com/aws-controllers-k8s/runtime/apis/core/v1alpha1"
	ackerr "github.com/aws-controllers-k8s/runtime/pkg/errors"
	acktypes "github.com/aws-controllers-k8s/runtime/pkg/types"

	svcapitypes "github.com/aws-controllers-k8s/ec2-controller/apis/v1alpha1"
)

// ClearResolvedReferences removes any reference values that were made
// concrete in the spec. It returns a copy of the input AWSResource which
// contains the original *Ref values, but none of their respective concrete
// values.
func (rm *resourceManager) ClearResolvedReferences(res acktypes.AWSResource) acktypes.AWSResource {
	ko := rm.concreteResource(res).ko.DeepCopy()

	for f0idx, f0iter := range ko.Spec.Associations {
		if f0iter.SubnetRef != nil {
			ko.Spec.Associations[f0idx].SubnetID = nil
		}
	}

	if ko.Spec.VPCRef != nil {
		ko.Spec.VPCID = nil
	}

	return &resource{ko}
}

// ResolveReferences finds if there are any Reference field(s) present
// inside AWSResource passed in the parameter and attempts to resolve those
// reference field(s) into their respective target field(s). It returns a
// copy of the input AWSResource with resolved reference(s), a boolean which
// is set to true if the resource contains any references (regardless of if
// they are resolved successfully) and an error if the passed AWSResource's
// reference field(s) could not be resolved.
func (rm *resourceManager) ResolveReferences(
	ctx context.Context,
	apiReader client.Reader,
	res acktypes.AWSResource,
) (acktypes.AWSResource, bool, error) {
	ko := rm.concreteResource(res).ko

	resourceHasReferences := false
	err := validateReferenceFields(ko)
	if fieldHasReferences, err := rm.resolveReferenceForAssociations_SubnetID(ctx, apiReader, ko); err != nil {
		return &resource{ko}, (resourceHasReferences || fieldHasReferences), err
	} else {
		resourceHasReferences = resourceHasReferences || fieldHasReferences
	}

	if fieldHasReferences, err := rm.resolveReferenceForVPCID(ctx, apiReader, ko); err != nil {
		return &resource{ko}, (resourceHasReferences || fieldHasReferences), err
	} else {
		resourceHasReferences = resourceHasReferences || fieldHasReferences
	}

	return &resource{ko}, resourceHasReferences, err
}

// validateReferenceFields validates the reference field and corresponding
// identifier field.
func validateReferenceFields(ko *svcapitypes.NetworkACL) error {

	for _, f0iter := range ko.Spec.Associations {
		if f0iter.SubnetRef != nil && f0iter.SubnetID != nil {
			return ackerr.ResourceReferenceAndIDNotSupportedFor("Associations.SubnetID", "Associations.SubnetRef")
		}
	}

	if ko.Spec.VPCRef != nil && ko.Spec.VPCID != nil {
		return ackerr.ResourceReferenceAndIDNotSupportedFor("VPCID", "VPCRef")
	}
	if ko.Spec.VPCRef == nil && ko.Spec.VPCID == nil {
		return ackerr.ResourceReferenceOrIDRequiredFor("VPCID", "VPCRef")
	}
	return nil
}

// resolveReferenceForAssociations_SubnetID reads the resource referenced
// from Associations.SubnetRef field and sets the Associations.SubnetID
// from referenced resource. Returns a boolean indicating whether a reference
// contains references, or an error
func (rm *resourceManager) resolveReferenceForAssociations_SubnetID(
	ctx context.Context,
	apiReader client.Reader,
	ko *svcapitypes.NetworkACL,
) (hasReferences bool, err error) {
	for f0idx, f0iter := range ko.Spec.Associations {
		if f0iter.SubnetRef != nil && f0iter.SubnetRef.From != nil {
			hasReferences = true
			arr := f0iter.SubnetRef.From
			if arr.Name == nil || *arr.Name == "" {
				return hasReferences, fmt.Errorf("provided resource reference is nil or empty: Associations.SubnetRef")
			}
			namespace := ko.ObjectMeta.GetNamespace()
			if arr.Namespace != nil && *arr.Namespace != "" {
				namespace = *arr.Namespace
			}
			obj := &svcapitypes.Subnet{}
			if err := getReferencedResourceState_Subnet(ctx, apiReader, obj, *arr.Name, namespace); err != nil {
				return hasReferences, err
			}
			ko.Spec.Associations[f0idx].SubnetID = (*string)(obj.Status.SubnetID)
		}
	}

	return hasReferences, nil
}

// getReferencedResourceState_Subnet looks up whether a referenced resource
// exists and is in a ACK.ResourceSynced=True state. If the referenced resource does exist and is
// in a Synced state, returns nil, otherwise returns `ackerr.ResourceReferenceTerminalFor` or
// `ResourceReferenceNotSyncedFor` depending on if the resource is in a Terminal state.
func getReferencedResourceState_Subnet(
	ctx context.Context,
	apiReader client.Reader,
	obj *svcapitypes.Subnet,
	name string, // the Kubernetes name of the referenced resource
	namespace string, // the Kubernetes namespace of the referenced resource
) error {
	namespacedName := types.NamespacedName{
		Namespace: namespace,
		Name:      name,
	}
	err := apiReader.Get(ctx, namespacedName, obj)
	if err != nil {
		return err
	}
	var refResourceSynced, refResourceTerminal bool
	for _, cond := range obj.Status.Conditions {
		if cond.Type == ackv1alpha1.ConditionTypeResourceSynced &&
			cond.Status == corev1.ConditionTrue {
			refResourceSynced = true
		}
		if cond.Type == ackv1alpha1.ConditionTypeTerminal &&
			cond.Status == corev1.ConditionTrue {
			return ackerr.ResourceReferenceTerminalFor(
				"Subnet",
				namespace, name)
		}
	}
	if refResourceTerminal {
		return ackerr.ResourceReferenceTerminalFor(
			"Subnet",
			namespace, name)
	}
	if !refResourceSynced {
		return ackerr.ResourceReferenceNotSyncedFor(
			"Subnet",
			namespace, name)
	}
	if obj.Status.SubnetID == nil {
		return ackerr.ResourceReferenceMissingTargetFieldFor(
			"Subnet",
			namespace, name,
			"Status.SubnetID")
	}
	return nil
}

// resolveReferenceForVPCID reads the resource referenced
// from VPCRef field and sets the VPCID
// from referenced resource. Returns a boolean indicating whether a reference
// contains references, or an error
func (rm *resourceManager) resolveReferenceForVPCID(
	ctx context.Context,
	apiReader client.Reader,
	ko *svcapitypes.NetworkACL,
) (hasReferences bool, err error) {
	if ko.Spec.VPCRef != nil && ko.Spec.VPCRef.From != nil {
		hasReferences = true
		arr := ko.Spec.VPCRef.From
		if arr.Name == nil || *arr.Name == "" {
			return hasReferences, fmt.Errorf("provided resource reference is nil or empty: VPCRef")
		}
		namespace := ko.ObjectMeta.GetNamespace()
		if arr.Namespace != nil && *arr.Namespace != "" {
			namespace = *arr.Namespace
		}
		obj := &svcapitypes.VPC{}
		if err := getReferencedResourceState_VPC(ctx, apiReader, obj, *arr.Name, namespace); err != nil {
			return hasReferences, err
		}
		ko.Spec.VPCID = (*string)(obj.Status.VPCID)
	}

	return hasReferences, nil
}

// getReferencedResourceState_VPC looks up whether a referenced resource
// exists and is in a ACK.ResourceSynced=True state. If the referenced resource does exist and is
// in a Synced state, returns nil, otherwise returns `ackerr.ResourceReferenceTerminalFor` or
// `ResourceReferenceNotSyncedFor` depending on if the resource is in a Terminal state.
func getReferencedResourceState_VPC(
	ctx context.Context,
	apiReader client.Reader,
	obj *svcapitypes.VPC,
	name string, // the Kubernetes name of the referenced resource
	namespace string, // the Kubernetes namespace of the referenced resource
) error {
	namespacedName := types.NamespacedName{
		Namespace: namespace,
		Name:      name,
	}
	err := apiReader.Get(ctx, namespacedName, obj)
	if err != nil {
		return err
	}
	var refResourceSynced, refResourceTerminal bool
	for _, cond := range obj.Status.Conditions {
		if cond.Type == ackv1alpha1.ConditionTypeResourceSynced &&
			cond.Status == corev1.ConditionTrue {
			refResourceSynced = true
		}
		if cond.Type == ackv1alpha1.ConditionTypeTerminal &&
			cond.Status == corev1.ConditionTrue {
			return ackerr.ResourceReferenceTerminalFor(
				"VPC",
				namespace, name)
		}
	}
	if refResourceTerminal {
		return ackerr.ResourceReferenceTerminalFor(
			"VPC",
			namespace, name)
	}
	if !refResourceSynced {
		return ackerr.ResourceReferenceNotSyncedFor(
			"VPC",
			namespace, name)
	}
	if obj.Status.VPCID == nil {
		return ackerr.ResourceReferenceMissingTargetFieldFor(
			"VPC",
			namespace, name,
			"Status.VPCID")
	}
	return nil
}
