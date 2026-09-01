from discovery.geocoder import CITY_COORDINATES, resolve_lead_coordinates


def test_resolve_exact_city():
    """Verify exact city name coordinate resolution."""
    coords = resolve_lead_coordinates(location="Chicago, IL", company_name="Apex Logistics")
    assert coords is not None
    # Base Chicago is (41.8781, -87.6298)
    assert abs(coords[0] - 41.8781) < 0.05
    assert abs(coords[1] - (-87.6298)) < 0.05


def test_resolve_international_cities():
    """Verify European and Middle Eastern metro coordinates resolution."""
    paris_coords = resolve_lead_coordinates(location="Paris, France")
    assert paris_coords is not None
    assert abs(paris_coords[0] - 48.8566) < 0.05

    dubai_coords = resolve_lead_coordinates(location="Dubai, UAE")
    assert dubai_coords is not None
    assert abs(dubai_coords[0] - 25.2048) < 0.05


def test_resolve_from_summary():
    """Verify extracting city from business summary when location is omitted."""
    coords = resolve_lead_coordinates(summary="Premier solar roofing contractor operating in Dallas and Fort Worth area.")
    assert coords is not None
    assert abs(coords[0] - 32.7767) < 0.05


def test_deterministic_spatial_jitter():
    """Verify that multiple leads in the same city produce slightly different coordinates so pins do not overlap."""
    coords1 = resolve_lead_coordinates(location="Chicago, IL", company_name="Company Alpha", lead_id="id-1")
    coords2 = resolve_lead_coordinates(location="Chicago, IL", company_name="Company Beta", lead_id="id-2")
    assert coords1 is not None and coords2 is not None
    assert coords1 != coords2
    # Still both within the Chicago metro radius
    assert abs(coords1[0] - coords2[0]) < 0.05


def test_metro_coordinates_registry():
    """Verify registry contains US, European, Middle Eastern, and Tunisian metro anchors."""
    assert "chicago" in CITY_COORDINATES
    assert "new york" in CITY_COORDINATES
    assert "london" in CITY_COORDINATES
    assert "paris" in CITY_COORDINATES
    assert "dubai" in CITY_COORDINATES
    assert "tunis" in CITY_COORDINATES
    assert "sfax" in CITY_COORDINATES
    assert "sousse" in CITY_COORDINATES
    assert "bizerte" in CITY_COORDINATES


def test_resolve_tunisia_locations():
    """Verify resolution of Tunisian cities, Arabic names, and country-level queries."""
    tunis_coords = resolve_lead_coordinates(location="Tunis, Tunisia")
    assert abs(tunis_coords[0] - 36.8065) < 0.05
    assert abs(tunis_coords[1] - 10.1815) < 0.05

    sfax_coords = resolve_lead_coordinates(location="Sfax, Tunisia")
    assert abs(sfax_coords[0] - 34.7406) < 0.05
    assert abs(sfax_coords[1] - 10.7603) < 0.05

    sousse_coords = resolve_lead_coordinates(location="Sousse")
    assert abs(sousse_coords[0] - 35.8256) < 0.05

    bizerte_arabic = resolve_lead_coordinates(location="بنزرت")
    assert abs(bizerte_arabic[0] - 37.2744) < 0.05

    tunisie_coords = resolve_lead_coordinates(location="Tunisie")
    assert abs(tunisie_coords[0] - 36.8065) < 0.05


def test_resolve_tld_domain():
    """Verify .tn domain maps to Tunisia even if location string is omitted."""
    coords = resolve_lead_coordinates(website_url="https://transfreight.tn/contact")
    assert abs(coords[0] - 36.8065) < 0.05
    assert abs(coords[1] - 10.1815) < 0.05


def test_wls_tunisia_overrides_chicago_fallback():
    """Verify WLS Tunisia (wls-tunisie.com) maps to Tunisia even when fallback is Chicago."""
    from discovery.geocoder import resolve_lead_location_label

    coords = resolve_lead_coordinates(
        company_name="WLS Tunisia",
        website_url="https://wls-tunisie.com",
        fallback_location="Chicago, IL",
    )
    assert abs(coords[0] - 36.8065) < 0.05
    assert abs(coords[1] - 10.1815) < 0.05

    label = resolve_lead_location_label(
        company_name="WLS Tunisia",
        website_url="https://wls-tunisie.com",
        fallback_location="Chicago, IL",
    )
    assert "Tunisia" in label
