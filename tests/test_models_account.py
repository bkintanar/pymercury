#!/usr/bin/env python3
"""
Unit tests for account models in pymercury.api.models.account
"""

import pytest
from pymercury.api.models.account import CustomerInfo, Account, Service, ServiceIds


class TestCustomerInfo:
    """Test CustomerInfo model"""

    def test_basic_initialization(self):
        """Test basic CustomerInfo initialization"""
        data = {
            'customerId': '123456',
            'name': 'John Smith',
            'email': 'john.smith@example.com'
        }
        customer = CustomerInfo(data)

        assert customer.customer_id == '123456'
        assert customer.name == 'John Smith'
        assert customer.email == 'john.smith@example.com'
        assert customer.raw_data == data

    def test_missing_fields(self):
        """Test CustomerInfo with missing fields"""
        data = {'customerId': '123456'}
        customer = CustomerInfo(data)

        assert customer.customer_id == '123456'
        assert customer.name is None
        assert customer.email is None


class TestAccount:
    """Test Account model"""

    def test_basic_initialization(self):
        """Test basic Account initialization"""
        data = {
            'accountId': '789012',
            'accountName': 'Main Account',
            'status': 'Active'
        }
        account = Account(data)

        assert account.account_id == '789012'
        assert account.account_name == 'Main Account'
        assert account.status == 'Active'

    def test_alternative_field_names(self):
        """Test Account with alternative field names"""
        data = {
            'id': '789012',
            'name': 'Main Account',
            'status': 'Active'
        }
        account = Account(data)

        assert account.account_id == '789012'
        assert account.account_name == 'Main Account'


class TestService:
    """Test Service model"""

    def test_electricity_service(self):
        """Test electricity Service initialization"""
        data = {
            'serviceId': 'E123456',
            'serviceGroup': 'electricity',
            'serviceType': 'Electricity',
            'address': '123 Main St',
            'status': 'Active'
        }
        service = Service(data)

        assert service.service_id == 'E123456'
        assert service.service_group == 'electricity'
        assert service.service_type == 'Electricity'
        assert service.address == '123 Main St'
        assert service.status == 'Active'

        # Test property methods
        assert service.is_electricity is True
        assert service.is_gas is False
        assert service.is_broadband is False

    def test_gas_service(self):
        """Test gas Service initialization"""
        data = {
            'serviceId': 'G789012',
            'serviceGroup': 'gas',
            'serviceType': 'Gas',
            'status': 'Active'
        }
        service = Service(data)

        assert service.is_electricity is False
        assert service.is_gas is True
        assert service.is_broadband is False

    def test_broadband_service(self):
        """Test broadband Service initialization"""
        data = {
            'serviceId': 'B345678',
            'serviceGroup': 'broadband',
            'serviceType': 'Broadband',
            'status': 'Active'
        }
        service = Service(data)

        assert service.is_electricity is False
        assert service.is_gas is False
        assert service.is_broadband is True

    def test_case_insensitive_service_group(self):
        """Test that serviceGroup is case-insensitive"""
        data = {
            'serviceId': 'E123456',
            'serviceGroup': 'ELECTRICITY',
            'serviceType': 'Electricity'
        }
        service = Service(data)

        assert service.service_group == 'electricity'
        assert service.is_electricity is True


class TestServiceIds:
    """Test ServiceIds container"""

    def test_empty_services(self):
        """Test ServiceIds with empty services list"""
        service_ids = ServiceIds([])

        assert service_ids.all == []
        assert service_ids.electricity == []
        assert service_ids.gas == []
        assert service_ids.broadband == []

    def test_mixed_services(self):
        """Test ServiceIds with mixed service types"""
        services = [
            Service({'serviceId': 'E123', 'serviceGroup': 'electricity'}),
            Service({'serviceId': 'G456', 'serviceGroup': 'gas'}),
            Service({'serviceId': 'B789', 'serviceGroup': 'broadband'}),
            Service({'serviceId': 'E101', 'serviceGroup': 'electricity'}),
        ]

        service_ids = ServiceIds(services)

        assert set(service_ids.all) == {'E123', 'G456', 'B789', 'E101'}
        assert set(service_ids.electricity) == {'E123', 'E101'}
        assert service_ids.gas == ['G456']
        assert service_ids.broadband == ['B789']

    def test_services_without_id(self):
        """Test ServiceIds with services that have no service ID"""
        services = [
            Service({'serviceGroup': 'electricity'}),  # No serviceId
            Service({'serviceId': 'E123', 'serviceGroup': 'electricity'}),
        ]

        service_ids = ServiceIds(services)

        assert service_ids.all == ['E123']
        assert service_ids.electricity == ['E123']
