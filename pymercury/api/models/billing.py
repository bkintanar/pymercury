#!/usr/bin/env python3
"""
Billing Models for Mercury.co.nz API

Contains billing, payment, and meter-related data classes.
"""

from typing import Dict, Any


class MeterInfo:
    """Electricity meter information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.account_id = data.get('accountId')

        # Extract meter services data (Mercury.co.nz API returns nested structure)
        self.meter_services = data.get('meterservices', [])

        # Extract electricity meter service data
        electricity_meter = None
        for service in self.meter_services:
            if service.get('serviceId'):  # This is likely the electricity service
                electricity_meter = service
                break

        if electricity_meter:
            self.service_id = electricity_meter.get('serviceId')
            self.smart_meter_installed = electricity_meter.get('smartMeterInstalled')
            self.smart_meter_communicating = electricity_meter.get('smartMeterCommunicating')
            # Use service ID as meter number for now
            self.meter_number = self.service_id
            self.meter_status = 'Active' if self.smart_meter_communicating else 'Not Communicating'
            self.meter_type = 'Smart Meter' if self.smart_meter_installed else 'Traditional Meter'
        else:
            self.service_id = None
            self.smart_meter_installed = None
            self.smart_meter_communicating = None
            self.meter_number = None
            self.meter_status = None
            self.meter_type = None

        # Legacy field mapping (keeping for backward compatibility)
        self.installation_date = data.get('installationDate')
        self.last_reading_date = data.get('lastReadingDate')
        self.next_reading_date = data.get('nextReadingDate')
        self.register_count = data.get('registerCount')
        self.registers = data.get('registers', [])

        # ICP (Installation Control Point) - unique identifier for electricity connections in NZ
        self.icp_number = data.get('icpNumber') or data.get('icp') or data.get('meter_number') or self.meter_number

        # Additional meter fields
        self.serial_number = data.get('serialNumber')
        self.location = data.get('location')
        self.manufacturer = data.get('manufacturer')
        self.model = data.get('model')
        # Add other meter fields as needed


class BillSummary:
    """Bill summary information container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.account_id = data.get('accountId')

        # Map Mercury.co.nz API field names to our standard names
        self.current_balance = data.get('balance')
        self.due_amount = data.get('dueAmount')
        self.overdue_amount = data.get('overdueAmount')
        self.due_date = data.get('dueDate')
        self.bill_date = data.get('billDate')  # Last bill date
        self.last_bill_date = data.get('billDate')  # Alias for backward compatibility
        self.next_bill_date = data.get('nextBillDate')

        # Payment information
        self.payment_method = data.get('paymentMethod')
        self.payment_type = data.get('paymentType')
        self.balance_status = data.get('balanceStatus')

        # Bill details
        self.bill_url = data.get('billUrl')
        self.smooth_pay = data.get('smoothPay')

        # Statement breakdown
        self.statement = data.get('statement', {})
        self.statement_details = self.statement.get('details', [])
        self.statement_total = self.statement.get('total')

        # Extract service costs from statement details
        self.electricity_amount = None
        self.gas_amount = None
        self.broadband_amount = None

        for detail in self.statement_details:
            line_item = detail.get('lineItem', '').lower()
            amount = detail.get('amount')
            if 'electricity' in line_item:
                self.electricity_amount = amount
            elif 'gas' in line_item:
                self.gas_amount = amount
            elif 'broadband' in line_item:
                self.broadband_amount = amount

        # Legacy fields for backward compatibility
        self.bill_frequency = data.get('billFrequency')
        self.recent_payments = data.get('recentPayments', [])
        self.recent_bills = data.get('recentBills', [])
        # Add other billing fields as needed
