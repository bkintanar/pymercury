"""Tests for electricity-specific models (Content, Summary, Plans, MeterReads)."""

import pytest

from pymercury.api.models import (
    ElectricityMeterReads,
    ElectricityPlans,
    ElectricitySummary,
    ElectricityUsageContent,
)


class TestElectricityUsageContent:
    def test_full_data(self):
        data = {
            "content": "<p>How to read your usage</p>",
            "path": "Electricity/Usage",
            "title": "Usage",
            "description": "Usage info",
            "usageData": [{"k": "v"}],
            "summaryInfo": {"x": 1},
        }
        c = ElectricityUsageContent(data)
        assert c.content == "<p>How to read your usage</p>"
        assert c.path == "Electricity/Usage"
        assert c.title == "Usage"
        assert c.description == "Usage info"
        assert c.usage_data == [{"k": "v"}]
        assert c.summary_info == {"x": 1}

    def test_empty_data(self):
        c = ElectricityUsageContent({})
        assert c.content is None
        assert c.usage_data == []
        assert c.summary_info == {}


class TestElectricitySummary:
    def test_with_weekly_usage_data(self):
        data = {
            "serviceType": "Electricity",
            "weeklySummary": {
                "startDate": "2026-04-13",
                "endDate": "2026-04-19",
                "notes": ["Note A"],
                "lastWeekCost": 42.10,
                "usage": [
                    {"consumption": 10, "cost": 5.00},
                    {"consumption": 20, "cost": 10.00},
                    {"consumption": 30, "cost": 15.00},
                ],
            },
            "monthlySummary": {
                "startDate": "2026-04-01",
                "endDate": "2026-04-30",
                "status": "current",
                "daysRemaining": 5,
                "usageCost": 200,
                "usageConsumption": 400,
                "note": "n/a",
            },
            "serviceId": "svc-1",
            "accountId": "acc-1",
            "asOfDate": "2026-04-26",
            "peakUsageTime": "evening",
            "offPeakUsage": 5,
            "billingPeriodStart": "2026-04-01",
            "billingPeriodEnd": "2026-04-30",
            "daysInPeriod": 30,
        }
        s = ElectricitySummary(data)
        assert s.weekly_total_usage == 60
        assert s.weekly_total_cost == 30.0
        assert s.weekly_usage_days == 3
        assert s.total_kwh_used == 60
        assert s.average_daily_usage == 20
        assert s.max_daily_usage == 30
        assert s.min_daily_usage == 10
        # HIGH-7 fix: these are now None, never fabricated.
        assert s.daily_fixed_charge is None
        assert s.gst_amount is None
        assert s.variable_charges == data["weeklySummary"]["usage"]
        # Monthly + legacy
        assert s.monthly_status == "current"
        assert s.peak_usage_time == "evening"
        assert s.days_in_period == 30

    def test_with_no_weekly_usage(self):
        s = ElectricitySummary({})
        assert s.weekly_total_usage == 0
        assert s.weekly_usage_days == 0
        assert s.total_kwh_used is None
        assert s.average_daily_usage is None
        assert s.daily_fixed_charge is None
        assert s.variable_charges == []
        assert s.gst_amount is None


class TestElectricityPlans:
    def test_with_full_plan_data(self):
        data = {
            "service_id": "svc-1",
            "account_id": "acc-1",
            "icp_number": "ICP-1",
            "canChangePlan": True,
            "pendingPlan": {
                "isPendingPlanChange": True,
                "planChangeDate": "2026-05-01",
            },
            "currentPlan": {
                "planId": "p1",
                "name": "Standard Anytime",
                "description": "Pay one rate, anytime",
                "usageType": "Anytime",
                "learnMore": "https://example.com",
                "charges": {
                    "otherCharges": [
                        {"name": "Other", "rate": 5},
                        {"name": "Daily Fixed Charge", "rate": 1.50},
                    ],
                    "unitRates": [
                        {"name": "Off-Peak", "rate": 0.10, "measure": "kWh"},
                        {"name": "Anytime", "rate": 0.30, "measure": "kWh"},
                    ],
                },
            },
            "standardPlans": [{"id": "sp1"}, {"id": "sp2"}],
            "lowPlans": [{"id": "lp1"}],
        }
        p = ElectricityPlans(data)
        assert p.service_id == "svc-1"
        assert p.account_id == "acc-1"
        assert p.icp_number == "ICP-1"
        assert p.can_change_plan is True
        assert p.is_pending_plan_change is True
        assert p.plan_change_date == "2026-05-01"
        assert p.current_plan_id == "p1"
        assert p.current_plan_name == "Standard Anytime"
        assert p.daily_fixed_charge == 1.50
        assert p.daily_fixed_charge_rate == 1.50
        assert p.anytime_rate == 0.30
        assert p.anytime_rate_measure == "kWh"
        assert p.total_alternative_plans == 3

    def test_with_camelcase_keys_for_ids(self):
        # Falls back to serviceId/accountId/icpNumber when snake_case absent
        p = ElectricityPlans({
            "serviceId": "svc-2",
            "accountId": "acc-2",
            "icpNumber": "ICP-2",
        })
        assert p.service_id == "svc-2"
        assert p.account_id == "acc-2"
        assert p.icp_number == "ICP-2"

    def test_icp_fallback_to_short_key(self):
        assert ElectricityPlans({"icp": "ICP-3"}).icp_number == "ICP-3"

    def test_when_charge_and_rate_names_missing(self):
        p = ElectricityPlans({
            "currentPlan": {
                "charges": {
                    "otherCharges": [{"name": "Different", "rate": 2}],
                    "unitRates": [{"name": "Peak", "rate": 0.5}],
                }
            }
        })
        assert p.daily_fixed_charge is None
        assert p.anytime_rate is None

    def test_with_empty_data(self):
        p = ElectricityPlans({})
        assert p.service_id is None
        assert p.icp_number is None
        assert p.can_change_plan is False
        assert p.standard_plans == []
        assert p.low_plans == []
        assert p.total_alternative_plans == 0


class TestElectricityMeterReads:
    def test_with_dict_meterreads_wrapper(self):
        data = {
            "accountId": "acc-1",
            "serviceId": "svc-1",
            "meterReads": [
                {
                    "meterNumber": "MN-1",
                    "registers": [
                        {
                            "registerNumber": "R1",
                            "lastReading": "12500",
                            "lastReadDate": "2026-04-20",
                            "lastReadType": "Actual",
                        }
                    ],
                }
            ],
        }
        r = ElectricityMeterReads(data)
        assert r.meter_number == "MN-1"
        assert r.account_id == "acc-1"
        assert r.service_id == "svc-1"
        assert r.latest_reading_value == "12500"
        assert r.latest_reading_date == "2026-04-20"
        assert r.latest_reading_type == "Actual"
        assert r.register_number == "R1"
        # HIGH-6 fix: previous reading and consumption are NOT fabricated.
        assert r.previous_reading_value is None
        assert r.consumption_kwh is None
        assert r.total_registers == 1
        assert r.total_reads == 1
        assert r.latest_reading_source == "automatic"  # Actual reading

    def test_with_estimated_reading_marks_source_as_estimated(self):
        data = {
            "meterReads": [
                {
                    "meterNumber": "MN-2",
                    "registers": [{"lastReading": "100", "lastReadType": "Estimated"}],
                }
            ]
        }
        r = ElectricityMeterReads(data)
        assert r.latest_reading_source == "estimated"

    def test_with_direct_list_input(self):
        data = [
            {
                "meterNumber": "MN-3",
                "registers": [{"lastReading": "555"}],
            }
        ]
        r = ElectricityMeterReads(data)
        assert r.meter_number == "MN-3"
        assert r.latest_reading_value == "555"

    def test_with_empty_meterreads(self):
        r = ElectricityMeterReads({"meterReads": []})
        assert r.meter_number is None
        assert r.latest_reading_value is None
        assert r.total_registers == 0
        assert r.consumption_kwh is None

    def test_with_unexpected_data_type(self):
        # Falls into the `else: meter_list = []` branch
        r = ElectricityMeterReads({"unexpected": "shape"})
        assert r.meter_number is None
        assert r.total_registers == 0

    def test_with_no_registers(self):
        data = {"meterReads": [{"meterNumber": "MN-no-regs"}]}
        r = ElectricityMeterReads(data)
        assert r.meter_number == "MN-no-regs"
        assert r.latest_reading_value is None
        assert r.register_number is None
