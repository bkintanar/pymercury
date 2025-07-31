#!/usr/bin/env python3
"""
Mercury.co.nz Library Utilities

Shared utility functions for the Mercury.co.nz library.
"""

import re
import json
import base64
import hashlib
import secrets
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, urlparse


def generate_pkce_verifier() -> str:
    """Generate a PKCE code verifier"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')


def generate_pkce_challenge(verifier: str) -> str:
    """Generate a PKCE code challenge from verifier"""
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')


def extract_from_html(html: str, pattern: str) -> str:
    """Extract data from HTML using regex pattern"""
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not extract required data from HTML using pattern: {pattern}")
    return match.group(1)


def parse_mercury_json(text: str) -> Optional[Dict[Any, Any]]:
    """Parse Mercury's malformed JSON responses"""
    for match in re.finditer(r'\{[^{}]*\}', text):
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            continue
    return None


def extract_auth_code_from_url(url: str) -> Optional[str]:
    """Extract authorization code from URL"""
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    return params.get('code', [None])[0]


def decode_jwt_payload(jwt_token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT payload without verification

    Args:
        jwt_token: The JWT token string

    Returns:
        Dictionary containing JWT claims, or None if invalid
    """
    try:
        # JWT structure: header.payload.signature
        parts = jwt_token.split('.')
        if len(parts) != 3:
            return None

        # Decode the payload (second part)
        payload = parts[1]

        # Add padding if necessary (JWT base64 encoding doesn't include padding)
        missing_padding = len(payload) % 4
        if missing_padding:
            payload += '=' * (4 - missing_padding)

        # Decode base64
        decoded_payload = base64.urlsafe_b64decode(payload)
        return json.loads(decoded_payload.decode('utf-8'))

    except Exception:
        return None


def extract_mercury_ids_from_jwt(claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract Mercury-specific IDs from JWT claims

    Args:
        claims: JWT claims dictionary

    Returns:
        Dictionary with extracted Mercury.co.nz IDs
    """
    extracted = {}

    # Mercury-specific claim mappings
    claim_mappings = {
        'customerId': ['extension_customerId', 'customerId', 'customer_id', 'sub'],
        'accountId': ['accountId', 'account_id'],
        'serviceId': ['serviceId', 'electricityServiceId', 'service_id']
    }

    for target_key, possible_keys in claim_mappings.items():
        for key in possible_keys:
            if key in claims:
                extracted[target_key] = claims[key]
                break

    # Also extract other useful claims
    useful_claims = ['iss', 'aud', 'exp', 'nbf', 'iat', 'email', 'name', 'given_name', 'family_name']
    for claim in useful_claims:
        if claim in claims:
            extracted[claim] = claims[claim]

    return extracted
