# One Convergence, Inc. CONFIDENTIAL
# Copyright (c) 2012-2015, One Convergence, Inc., USA
# All Rights Reserved.
#
# All information contained herein is, and remains the property of
# One Convergence, Inc. and its suppliers, if any. The intellectual and
# technical concepts contained herein are proprietary to One Convergence,
# Inc. and its suppliers.
#
# Dissemination of this information or reproduction of this material is
# strictly forbidden unless prior written permission is obtained from
# One Convergence, Inc., USA

""" Defines various types of constants used across all modules
    in elastic services."""

service_timeout_s = 900


"""TOPIC names for RPC communication."""
SERVICE_MANAGER_RPC_TOPIC = "topics_ocmanager_agent"

"""Device states."""
NEW = "NEW"
ACTIVE = "ACTIVE"
PENDING_CREATE = "PENDING_CREATE"
PENDING_UPDATE = "PENDING_UPDATE"
PENDING_DELETE = "PENDING_DELETE"
ERROR = "ERROR"

"""Openstack Driver Options"""
DEFAULT_OS_CONTROLLER_IP = "127.0.0.1"

DEFAULT_ADMIN_API_SERVER_PORT = 35357
DEFAULT_ADMIN_API_VERSION = "v2.0"

DEFAULT_COMPUTE_SERVER_PORT = 8774
DEFAULT_COMPUTE_API_VERSION = "v2"

DEFAULT_IDENTITY_SERVER_PORT = 5000
DEFAULT_IDENTITY_API_VERSION = "v2.0"

DEFAULT_NETWORK_SERVER_PORT = 9696
DEFAULT_NETWORK_API_VERSION = "v2.0"

"""service Types"""
LOADBALANCER = "LOADBALANCER"
FIREWALL = "FIREWALL"
VPN = "VPN"

FWAAS_VM_AGENT = "8888"
LBAAS_VM_AGENT = "1234"
ONECONVERGENCE_VM_AGENT = "8888"
ASAV_AGENT = "443"
DEFAULT_WEB_AGENT = "80"

EAST_WEST = 'east_west'
NORTH_SOUTH = 'north_south'

APP_NAME = "SERVICES"
ES_OPENSTACK_DRIVER = "SERVICES_OPENSTACK_DRIVER"
PROJECT = "services"

EXTERNAL_NETWORK_NAME = 'service-mgmt'

firewall_agent_topic = 'oc-firewall-agent'
vpn_agent_topic = 'oc-vpn-agent'

"""HA VM State"""
ACTIVE_VM = "ACTIVE_VM"
STANDBY_VM = "STANDBY_VM"  

