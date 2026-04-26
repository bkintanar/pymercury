"""Tests for billing models (MeterInfo, BillSummary)."""

import pytest

from pymercury.api.models import BillSummary, MeterInfo


class TestMeterInfo:
    def test_with_communicating_smart_meter(self):
        data = {
            "accountId": "acc-1",
            "meterservices": [
                {
                    "serviceId": "svc-electric-1",
                    "smartMeterInstalled": True,
                    "smartMeterCommunicating": True,
                }
            ],
            "icpNumber": "ICP-1234567890",
            "installationDate": "2020-01-01",
            "lastReadingDate": "2026-04-20",
            "nextReadingDate": "2026-05-20",
            "registerCount": 1,
            "registers": [{"registerNumber": "R1"}],
            "serialNumber": "SN-001",
            "location": "Front of house",
            "manufacturer": "ACME",
            "model": "Smart-3000",
        }
        info = MeterInfo(data)
        assert info.account_id == "acc-1"
        assert info.service_id == "svc-electric-1"
        assert info.smart_meter_installed is True
        assert info.smart_meter_communicating is True
        assert info.meter_number == "svc-electric-1"
        assert info.meter_status == "Active"
        assert info.meter_type == "Smart Meter"
        assert info.icp_number == "ICP-1234567890"
        assert info.serial_number == "SN-001"
        assert info.location == "Front of house"

    def test_with_non_communicating_traditional_meter(self):
        data = {
            "meterservices": [
                {
                    "serviceId": "svc-2",
                    "smartMeterInstalled": False,
                    "smartMeterCommunicating": False,
                }
            ]
        }
        info = MeterInfo(data)
        assert info.meter_status == "Not Communicating"
        assert info.meter_type == "Traditional Meter"

    def test_with_no_matching_service_returns_none_fields(self):
        data = {
            "meterservices": [
                {"smartMeterInstalled": True}  # missing serviceId
            ]
        }
        info = MeterInfo(data)
        assert info.service_id is None
        assert info.smart_meter_installed is None
        assert info.smart_meter_communicating is None
        assert info.meter_number is None
        assert info.meter_status is None
        assert info.meter_type is None

    def test_with_empty_data_returns_none_fields(self):
        info = MeterInfo({})
        assert info.account_id is None
        assert info.meter_services == []
        assert info.service_id is None
        assert info.icp_number is None

    def test_icp_number_fallback_chain(self):
        # icpNumber > icp > meter_number > self.meter_number (set above)
        data1 = {"icp": "ICP-FALLBACK-1"}
        assert MeterInfo(data1).icp_number == "ICP-FALLBACK-1"
        data2 = {"meter_number": "MN-FALLBACK"}
        assert MeterInfo(data2).icp_number == "MN-FALLBACK"


class TestBillSummary:
    def test_full_statement_with_all_three_services(self):
        data = {
            "accountId": "acc-1",
            "balance": 234.56,
            "dueAmount": 100.00,
            "overdueAmount": 0.0,
            "dueDate": "2026-05-15",
            "billDate": "2026-04-20",
            "nextBillDate": "2026-05-20",
            "paymentMethod": "DirectDebit",
            "paymentType": "Monthly",
            "balanceStatus": "OK",
            "billUrl": "https://example.com/bill.pdf",
            "smoothPay": True,
            "statement": {
                "total": 234.56,
                "details": [
                    {"lineItem": "Electricity Charges", "amount": 150.00},
                    {"lineItem": "Gas charges", "amount": 50.00},
                    {"lineItem": "Broadband fee", "amount": 34.56},
                ],
            },
            "billFrequency": "Monthly",
            "recentPayments": [{"amount": 100}],
            "recentBills": [{"id": "b1"}],
        }
        bs = BillSummary(data)
        assert bs.current_balance == 234.56
        assert bs.due_amount == 100.0
        assert bs.bill_date == "2026-04-20"
        assert bs.last_bill_date == "2026-04-20"
        assert bs.next_bill_date == "2026-05-20"
        assert bs.electricity_amount == 150.0
        assert bs.gas_amount == 50.0
        assert bs.broadband_amount == 34.56
        assert bs.statement_total == 234.56
        assert bs.bill_frequency == "Monthly"
        assert len(bs.recent_payments) == 1

    def test_missing_statement_yields_none_amounts(self):
        bs = BillSummary({"balance": 0})
        assert bs.statement == {}
        assert bs.statement_details == []
        assert bs.electricity_amount is None
        assert bs.gas_amount is None
        assert bs.broadband_amount is None

    def test_unrecognized_line_item_does_not_set_amount(self):
        data = {
            "statement": {
                "details": [{"lineItem": "Other", "amount": 10}]
            }
        }
        bs = BillSummary(data)
        assert bs.electricity_amount is None
        assert bs.gas_amount is None
        assert bs.broadband_amount is None


class TestGasUsageContent:
    def test_full_content(self):
        from pymercury.api.models import GasUsageContent

        data = {
            "contentName": "GasUsage",
            "locale": "en-NZ",
            "content": {
                "disclaimer_usage": {"text": "Estimated"},
                "usage_info_modal_title": {"text": "About usage"},
                "usage_info_modal_body": {"text": "Long body"},
            },
        }
        c = GasUsageContent(data)
        assert c.content_name == "GasUsage"
        assert c.locale == "en-NZ"
        assert c.disclaimer_usage == "Estimated"
        assert c.usage_info_modal_title == "About usage"
        assert c.usage_info_modal_body == "Long body"

    def test_empty_content(self):
        from pymercury.api.models import GasUsageContent

        c = GasUsageContent({})
        assert c.content == {}
        assert c.disclaimer_usage == ""
        assert c.usage_info_modal_title == ""
        assert c.usage_info_modal_body == ""


class TestServiceIdsMisc:
    def test_service_id_belongs_to_unrecognized_group(self):
        """A service whose group is none of electricity/gas/broadband still
        contributes to .all but to no typed list — exercises the elif chain
        falling through with no match."""
        from pymercury.api.models import Service, ServiceIds

        services = [
            Service({
                "serviceId": "svc-fibre",
                "serviceGroup": "fibre",  # not "broadband"
                "serviceType": "Fibre",
            })
        ]
        ids = ServiceIds(services)
        assert ids.all == ["svc-fibre"]
        assert ids.electricity == []
        assert ids.gas == []
        assert ids.broadband == []
