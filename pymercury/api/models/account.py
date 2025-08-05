#!/usr/bin/env python3
"""
Account Models for Mercury.co.nz API

Contains customer, account, and service-related data classes.
"""

from typing import Dict, Any, List


class CustomerInfo:
    """Customer information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.customer_id = data.get('customerId')
        self.name = data.get('name')
        self.email = data.get('email')
        # Add other customer fields as needed


class Account:
    """Customer account container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.account_id = data.get('accountId') or data.get('id')
        self.account_name = data.get('accountName') or data.get('name')
        self.status = data.get('status')
        # Add other account fields as needed


class Service:
    """Service container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.service_id = data.get('serviceId')
        self.service_group = data.get('serviceGroup', '').lower()
        self.service_type = data.get('serviceType')
        self.address = data.get('address')
        self.status = data.get('status')
        # Add other service fields as needed

    @property
    def is_electricity(self) -> bool:
        """Check if this is an electricity service"""
        return self.service_group == 'electricity'

    @property
    def is_gas(self) -> bool:
        """Check if this is a gas service"""
        return self.service_group == 'gas'

    @property
    def is_broadband(self) -> bool:
        """Check if this is a broadband service"""
        return self.service_group == 'broadband'


class ServiceIds:
    """Container for organized service IDs"""

    def __init__(self, services: List[Service]):
        self.all: List[str] = []
        self.electricity: List[str] = []
        self.gas: List[str] = []
        self.broadband: List[str] = []

        for service in services:
            if service.service_id:
                self.all.append(service.service_id)

                if service.is_electricity:
                    self.electricity.append(service.service_id)
                elif service.is_gas:
                    self.gas.append(service.service_id)
                elif service.is_broadband:
                    self.broadband.append(service.service_id)
