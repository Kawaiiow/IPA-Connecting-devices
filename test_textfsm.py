"""test_textfsm.py - Pytest test suite for textfsmlab.py based on network topology.

Tests both the logic for parsing/generating interface descriptions and the live
configured interface descriptions on R1, R2, and S1 using Netmiko and TextFSM.
"""

import pytest
from netmiko import ConnectHandler

from textfsmlab import (
    DEVICES,
    shorten_interface,
    normalize_interface,
    clean_device_name,
    format_cdp_description,
    generate_descriptions,
    get_interface_descriptions,
)


# ==============================================================================
# Unit Tests (TDD Logic Verification)
# ==============================================================================


def test_shorten_interface():
    """Verify interface names are shortened according to Cisco conventions."""
    assert shorten_interface("GigabitEthernet0/1") == "G0/1"
    assert shorten_interface("Gig 0/1") == "G0/1"
    assert shorten_interface("GigabitEthernet0/2") == "G0/2"
    assert shorten_interface("FastEthernet0/1") == "Fa0/1"
    assert shorten_interface("Loopback0") == "Lo0"


def test_clean_device_name():
    """Verify domain suffixes are stripped from device hostnames."""
    assert clean_device_name("R2.ipa.com") == "R2"
    assert clean_device_name("S0.ipa.com") == "S0"
    assert clean_device_name("S1.npa.com") == "S1"
    assert clean_device_name("R1") == "R1"


def test_format_cdp_description():
    """Verify formatted description matches 'Connect to <Interface-name> of <Remote device name>'."""
    desc = format_cdp_description("GigabitEthernet0/1", "R2.ipa.com")
    assert desc == "Connect to G0/1 of R2"

    desc2 = format_cdp_description("Gig 0/2", "S1.ipa.com")
    assert desc2 == "Connect to G0/2 of S1"


def test_generate_descriptions_r1():
    """Verify R1 description generation for control/data plane."""
    mock_cdp = [
        {"local_interface": "GigabitEthernet0/1", "neighbor_name": "R2.ipa.com", "neighbor_interface": "GigabitEthernet0/1"},
        {"local_interface": "GigabitEthernet0/0", "neighbor_name": "S0.ipa.com", "neighbor_interface": "GigabitEthernet0/1"},
    ]
    descriptions = generate_descriptions("R1", mock_cdp)

    # R2 link
    assert descriptions.get("Gi0/1") == "Connect to G0/1 of R2"
    # PC link
    assert descriptions.get("Gi0/2") == "Connect to PC"


def test_generate_descriptions_r2():
    """Verify R2 description generation for control/data plane including WAN."""
    mock_cdp = [
        {"local_interface": "GigabitEthernet0/1", "neighbor_name": "R1.ipa.com", "neighbor_interface": "GigabitEthernet0/1"},
        {"local_interface": "GigabitEthernet0/2", "neighbor_name": "S1.ipa.com", "neighbor_interface": "GigabitEthernet0/1"},
    ]
    descriptions = generate_descriptions("R2", mock_cdp)

    assert descriptions.get("Gi0/1") == "Connect to G0/1 of R1"
    assert descriptions.get("Gi0/2") == "Connect to G0/1 of S1"
    # Interface G0/3 is DHCP / WAN client
    assert descriptions.get("Gi0/3") == "Connect to WAN"


def test_generate_descriptions_s1():
    """Verify S1 description generation for control/data plane."""
    mock_cdp = [
        {"local_interface": "GigabitEthernet0/1", "neighbor_name": "R2.ipa.com", "neighbor_interface": "GigabitEthernet0/2"},
    ]
    descriptions = generate_descriptions("S1", mock_cdp)

    assert descriptions.get("Gi0/1") == "Connect to G0/2 of R2"
    assert descriptions.get("Gi1/1") == "Connect to PC"


# ==============================================================================
# Live Device Verification Tests (TextFSM on Live Cisco IOS Devices)
# ==============================================================================


@pytest.fixture(scope="module")
def r1_descriptions():
    conn = ConnectHandler(**DEVICES["R1"])
    descs = get_interface_descriptions(conn)
    conn.disconnect()
    return descs


@pytest.fixture(scope="module")
def r2_descriptions():
    conn = ConnectHandler(**DEVICES["R2"])
    descs = get_interface_descriptions(conn)
    conn.disconnect()
    return descs


@pytest.fixture(scope="module")
def s1_descriptions():
    conn = ConnectHandler(**DEVICES["S1"])
    descs = get_interface_descriptions(conn)
    conn.disconnect()
    return descs


def test_r1_live_descriptions(r1_descriptions):
    """Verify R1 interface descriptions on live device using TextFSM."""
    # Check that the interface connected to R2 has the CDP description
    r2_connected = (
        r1_descriptions.get("Gi0/1") == "Connect to G0/1 of R2"
        or r1_descriptions.get("Gi0/2") == "Connect to G0/1 of R2"
    )
    assert r2_connected, f"R1 missing connection to R2 in descriptions: {r1_descriptions}"

    # Check that the interface connected to PC has 'Connect to PC'
    pc_connected = (
        r1_descriptions.get("Gi0/1") == "Connect to PC"
        or r1_descriptions.get("Gi0/2") == "Connect to PC"
    )
    assert pc_connected, f"R1 missing connection to PC in descriptions: {r1_descriptions}"


def test_r2_live_descriptions(r2_descriptions):
    """Verify R2 interface descriptions on live device using TextFSM."""
    # WAN interface G0/3
    assert r2_descriptions.get("Gi0/3") == "Connect to WAN"

    # Connection to R1
    assert r2_descriptions.get("Gi0/1") in ("Connect to G0/1 of R1", "Connect to G0/2 of R1")

    # Connection to S1
    assert r2_descriptions.get("Gi0/2") in ("Connect to G0/1 of S1", "Connect to G0/2 of S1")


def test_s1_live_descriptions(s1_descriptions):
    """Verify S1 interface descriptions on live device using TextFSM."""
    # Connection to R2
    assert s1_descriptions.get("Gi0/1") in ("Connect to G0/2 of R2", "Connect to G0/1 of R2")

    # Connection to PC
    assert s1_descriptions.get("Gi1/1") == "Connect to PC"
