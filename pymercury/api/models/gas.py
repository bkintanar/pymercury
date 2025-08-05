#!/usr/bin/env python3
"""
Gas Models for Mercury.co.nz API

Contains gas-specific data classes and models.
"""

from typing import Dict, Any
from .base import ServiceUsage


class GasUsageContent:
    """Gas usage content container"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data
        self.content_name = data.get('contentName')
        self.locale = data.get('locale')
        self.content = data.get('content', {})

        # Parse specific gas usage content fields
        content_data = self.content
        self.disclaimer_usage = content_data.get('disclaimer_usage', {}).get('text', '')
        self.usage_info_modal_title = content_data.get('usage_info_modal_title', {}).get('text', '')
        self.usage_info_modal_body = content_data.get('usage_info_modal_body', {}).get('text', '')


class GasUsage(ServiceUsage):
    """Gas usage data container"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)
