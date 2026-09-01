"""Zero-cost local geocoding resolver and city coordinate mapping with international support."""

from __future__ import annotations

import hashlib
import re

# Specific City & Metropolitan Coordinates (tested first)
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    # --------------------------------------------------------------------------
    # Tunisia Cities & Metros (Multilingual: EN / FR / AR)
    # --------------------------------------------------------------------------
    "sfax": (34.7406, 10.7603),
    "صفاقس": (34.7406, 10.7603),
    "sousse": (35.8256, 10.6369),
    "سوسة": (35.8256, 10.6369),
    "bizerte": (37.2744, 9.8739),
    "بنزرت": (37.2744, 9.8739),
    "ariana": (36.8665, 10.1647),
    "أريانة": (36.8665, 10.1647),
    "monastir": (35.7780, 10.8262),
    "المنستير": (35.7780, 10.8262),
    "nabeul": (36.4561, 10.7376),
    "نابل": (36.4561, 10.7376),
    "hammamet": (36.4000, 10.6167),
    "الحمامات": (36.4000, 10.6167),
    "gabes": (33.8815, 10.0982),
    "قابس": (33.8815, 10.0982),
    "kairouan": (35.6781, 10.0963),
    "القيروان": (35.6781, 10.0963),
    "la marsa": (36.8782, 10.3247),
    "marsa": (36.8782, 10.3247),
    "المرسى": (36.8782, 10.3247),
    "carthage": (36.8530, 10.3230),
    "قرطاج": (36.8530, 10.3230),
    "berges du lac": (36.8333, 10.2333),
    "les berges du lac": (36.8333, 10.2333),
    "lac 1": (36.8333, 10.2333),
    "lac 2": (36.8380, 10.2500),
    "rades": (36.7681, 10.2753),
    "radès": (36.7681, 10.2753),
    "رادس": (36.7681, 10.2753),
    "ben arous": (36.7531, 10.2189),
    "بن عروس": (36.7531, 10.2189),
    "manouba": (36.8081, 10.0972),
    "منوبة": (36.8081, 10.0972),
    "mahdia": (35.5047, 11.0622),
    "المهدية": (35.5047, 11.0622),
    "djerba": (33.8076, 10.8451),
    "جربة": (33.8076, 10.8451),
    "zarzis": (33.5040, 11.1122),
    "جرجيس": (33.5040, 11.1122),
    "gafsa": (34.4250, 8.7842),
    "قفصة": (34.4250, 8.7842),
    "tozeur": (33.9197, 8.1335),
    "توزر": (33.9197, 8.1335),
    "beja": (36.7256, 9.1817),
    "béja": (36.7256, 9.1817),
    "باجة": (36.7256, 9.1817),
    "jendouba": (36.5011, 8.7802),
    "جندوبة": (36.5011, 8.7802),
    "le kef": (36.1822, 8.7149),
    "الكاف": (36.1822, 8.7149),
    "tunis": (36.8065, 10.1815),

    # --------------------------------------------------------------------------
    # Other Middle East & North Africa Metros
    # --------------------------------------------------------------------------
    "casablanca": (33.5731, -7.5898),
    "rabat": (34.0209, -6.8416),
    "marrakech": (31.6295, -7.9811),
    "tanger": (35.7595, -5.8340),
    "tangier": (35.7595, -5.8340),
    "algiers": (36.7538, 3.0588),
    "oran": (35.6987, -0.6349),
    "cairo": (30.0444, 31.2357),
    "alexandria": (31.2001, 29.9187),
    "dubai": (25.2048, 55.2708),
    "abu dhabi": (24.4539, 54.3773),
    "sharjah": (25.3463, 55.4209),
    "riyadh": (24.7136, 46.6753),
    "jeddah": (21.4858, 39.1925),
    "dammam": (26.4207, 50.0888),
    "doha": (25.2854, 51.5310),
    "kuwait": (29.3759, 47.9774),
    "manama": (26.2285, 50.5860),
    "muscat": (23.5880, 58.3829),
    "beirut": (33.8938, 35.5018),
    "amman": (31.9454, 35.9284),
    "istanbul": (41.0082, 28.9784),

    # --------------------------------------------------------------------------
    # US Metros
    # --------------------------------------------------------------------------
    "chicago": (41.8781, -87.6298),
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "la": (34.0522, -118.2437),
    "dallas": (32.7767, -96.7970),
    "fort worth": (32.7555, -97.3308),
    "houston": (29.7604, -95.3698),
    "austin": (30.2672, -97.7431),
    "san antonio": (29.4241, -98.4936),
    "miami": (25.7617, -80.1918),
    "orlando": (28.5383, -81.3792),
    "tampa": (27.9506, -82.4572),
    "atlanta": (33.7490, -84.3880),
    "san francisco": (37.7749, -122.4194),
    "sf": (37.7749, -122.4194),
    "san jose": (37.3382, -121.8863),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "phoenix": (33.4484, -112.0740),
    "boston": (42.3601, -71.0589),
    "philadelphia": (39.9526, -75.1652),
    "washington": (38.9072, -77.0369),
    "dc": (38.9072, -77.0369),
    "charlotte": (35.2271, -80.8431),
    "nashville": (36.1627, -86.7816),
    "las vegas": (36.1699, -115.1398),
    "san diego": (32.7157, -117.1611),
    "minneapolis": (44.9778, -93.2650),
    "detroit": (42.3314, -83.0458),
    "cleveland": (41.4993, -81.6944),
    "columbus": (39.9612, -82.9988),
    "indianapolis": (39.7684, -86.1581),
    "kansas city": (39.0997, -94.5786),
    "st louis": (38.6270, -90.1994),
    "pittsburgh": (40.4406, -79.9959),
    "baltimore": (39.2904, -76.6122),
    "portland": (45.5152, -122.6784),
    "salt lake city": (40.7608, -111.8910),
    "memphis": (35.1495, -90.0490),
    "louisville": (38.2527, -85.7585),
    "milwaukee": (43.0389, -87.9065),
    "oklahoma city": (35.4676, -97.5164),
    "raleigh": (35.7796, -78.6382),

    # --------------------------------------------------------------------------
    # European Metros
    # --------------------------------------------------------------------------
    "paris": (48.8566, 2.3522),
    "london": (51.5074, -0.1278),
    "berlin": (52.5200, 13.4050),
    "munich": (48.1351, 11.5820),
    "frankfurt": (50.1109, 8.6821),
    "madrid": (40.4168, -3.7038),
    "barcelona": (41.3851, 2.1734),
    "rome": (41.9028, 12.4964),
    "milan": (45.4642, 9.1900),
    "amsterdam": (52.3676, 4.9041),
    "rotterdam": (51.9244, 4.4777),
    "brussels": (50.8503, 4.3517),
    "zurich": (47.3769, 8.5417),
    "geneva": (46.2044, 6.1432),
    "vienna": (48.2082, 16.3738),
    "dublin": (53.3498, -6.2603),
    "lisbon": (38.7223, -9.1393),
    "warsaw": (52.2297, 21.0122),
    "prague": (50.0755, 14.4378),
    "stockholm": (59.3293, 18.0686),
    "copenhagen": (55.6761, 12.5683),
    "oslo": (59.9139, 10.7522),
    "helsinki": (60.1699, 24.9384),
    "lyon": (45.7640, 4.8357),
    "marseille": (43.2965, 5.3698),
    "bordeaux": (44.8378, -0.5792),
    "toulouse": (43.6047, 1.4442),
    "nice": (43.7102, 7.2620),
    "nantes": (47.2184, -1.5536),
    "strasbourg": (48.5734, 7.7521),
    "lille": (50.6292, 3.0573),

    # --------------------------------------------------------------------------
    # Other Global Metros
    # --------------------------------------------------------------------------
    "toronto": (43.6532, -79.3832),
    "montreal": (45.5017, -73.5673),
    "vancouver": (49.2827, -123.1207),
    "sydney": (33.8688, 151.2093),
    "melbourne": (37.8136, 144.9631),
    "singapore": (1.3521, 103.8198),
    "tokyo": (35.6762, 139.6503),
}

# Country-Level Coordinates (tested second if no specific city matches)
COUNTRY_COORDINATES: dict[str, tuple[float, float]] = {
    "tunisia": (36.8065, 10.1815),
    "tunisie": (36.8065, 10.1815),
    "تونس": (36.8065, 10.1815),
    "morocco": (33.5731, -7.5898),
    "maroc": (33.5731, -7.5898),
    "المغرب": (33.5731, -7.5898),
    "algeria": (36.7538, 3.0588),
    "algérie": (36.7538, 3.0588),
    "الجزائر": (36.7538, 3.0588),
    "egypt": (30.0444, 31.2357),
    "مصر": (30.0444, 31.2357),
    "uae": (25.2048, 55.2708),
    "emirates": (25.2048, 55.2708),
    "الإمارات": (25.2048, 55.2708),
    "saudi arabia": (24.7136, 46.6753),
    "saudi": (24.7136, 46.6753),
    "السعودية": (24.7136, 46.6753),
    "france": (48.8566, 2.3522),
    "germany": (52.5200, 13.4050),
    "united kingdom": (51.5074, -0.1278),
    "uk": (51.5074, -0.1278),
    "united states": (39.8283, -98.5795),
    "usa": (39.8283, -98.5795),
    "canada": (45.5017, -73.5673),
}

# Country TLD fallback mappings
TLD_COUNTRY_COORDINATES: dict[str, tuple[float, float]] = {
    ".tn": (36.8065, 10.1815),    # Tunisia
    ".fr": (48.8566, 2.3522),     # France
    ".ma": (33.5731, -7.5898),    # Morocco
    ".dz": (36.7538, 3.0588),     # Algeria
    ".eg": (30.0444, 31.2357),    # Egypt
    ".ae": (25.2048, 55.2708),    # UAE
    ".sa": (24.7136, 46.6753),    # Saudi Arabia
    ".qa": (25.2854, 51.5310),    # Qatar
    ".kw": (29.3759, 47.9774),    # Kuwait
    ".uk": (51.5074, -0.1278),    # United Kingdom
    ".de": (52.5200, 13.4050),    # Germany
    ".es": (40.4168, -3.7038),    # Spain
    ".it": (41.9028, 12.4964),    # Italy
    ".ca": (45.5017, -73.5673),    # Canada
}


def resolve_lead_location_label(
    location: str | None = None,
    company_name: str | None = None,
    website_url: str | None = None,
    summary: str | None = None,
    fallback_location: str | None = None,
) -> str:
    """Resolve an accurate, human-readable location label for a lead.

    Evaluates the lead's own identity (company name, domain, email, summary) FIRST
    to prevent false fallbacks to campaign default locations.
    """
    lead_text = f"{location or ''} {company_name or ''} {summary or ''}".lower()
    clean_url = (
        str(website_url or "")
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )
    url_tokens = set(re.split(r"[\W_.-]+", clean_url))

    # 1. Check Country Code TLD on website URL
    for tld in TLD_COUNTRY_COORDINATES:
        if clean_url.endswith(tld) or tld[1:] in url_tokens:
            if tld == ".tn":
                return "Tunis, Tunisia"
            return tld[1:].upper()

    # 2. Direct city check in lead text or tokenized URL
    sorted_cities = sorted(CITY_COORDINATES.keys(), key=len, reverse=True)
    for city_key in sorted_cities:
        if (
            re.search(rf"\b{re.escape(city_key)}\b", lead_text)
            or city_key in url_tokens
            or (len(city_key) >= 4 and city_key.replace(" ", "") in clean_url)
        ):
            title_city = city_key.title()
            if title_city.lower() in [
                "sfax", "sousse", "bizerte", "ariana", "monastir", "nabeul", "hammamet",
                "gabes", "kairouan", "la marsa", "carthage", "rades", "ben arous", "manouba",
                "mahdia", "djerba", "zarzis", "gafsa", "tozeur", "beja", "jendouba",
            ]:
                return f"{title_city}, Tunisia"
            if title_city.lower() in ["tunis"]:
                return "Tunis, Tunisia"
            if title_city.lower() in ["paris", "lyon", "marseille", "bordeaux", "toulouse", "nice", "nantes", "strasbourg", "lille"]:
                return f"{title_city}, France"
            return title_city

    # 3. Direct country check in lead text or tokenized URL
    sorted_countries = sorted(COUNTRY_COORDINATES.keys(), key=len, reverse=True)
    for country_key in sorted_countries:
        if (
            re.search(rf"\b{re.escape(country_key)}\b", lead_text)
            or country_key in url_tokens
            or (len(country_key) >= 4 and country_key.replace(" ", "") in clean_url)
        ):
            if country_key in ["tunisia", "tunisie", "تونس"]:
                return "Tunis, Tunisia"
            return country_key.title()

    # 4. Dialing codes
    if "+216" in lead_text or "216 " in lead_text or "(216)" in lead_text:
        return "Tunis, Tunisia"
    if "+33" in lead_text or "0033" in lead_text:
        return "Paris, France"
    if "+212" in lead_text:
        return "Casablanca, Morocco"

    # 5. Explicit location string if provided
    if location and location.strip():
        return location.strip()

    # 6. Fallback location
    if fallback_location and fallback_location.strip():
        return fallback_location.strip()

    return "Tunis, Tunisia"


def resolve_lead_coordinates(
    location: str | None = None,
    summary: str | None = None,
    company_name: str | None = None,
    website_url: str | None = None,
    lead_id: str | None = None,
    fallback_location: str | None = None,
) -> tuple[float, float]:
    """Resolve latitude and longitude coordinates for a lead with deterministic spatial jitter.

    Evaluates the lead's own identity (company name, domain, summary, explicit location)
    BEFORE consulting fallback_location.
    """
    lead_text = f"{location or ''} {company_name or ''} {summary or ''}".lower()
    clean_url = (
        str(website_url or "")
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )
    url_tokens = set(re.split(r"[\W_.-]+", clean_url))

    base_coords: tuple[float, float] | None = None

    # 1. Check Country Code TLD on website URL
    for tld, coords in TLD_COUNTRY_COORDINATES.items():
        if clean_url.endswith(tld) or tld[1:] in url_tokens:
            base_coords = coords
            break

    # 2. Match specific city in lead text or URL tokens
    if not base_coords:
        sorted_cities = sorted(CITY_COORDINATES.items(), key=lambda x: len(x[0]), reverse=True)
        for city_key, coords in sorted_cities:
            if (
                re.search(rf"\b{re.escape(city_key)}\b", lead_text)
                or city_key in url_tokens
                or (len(city_key) >= 4 and city_key.replace(" ", "") in clean_url)
            ):
                base_coords = coords
                break

    # 3. Match broader country in lead text or URL tokens
    if not base_coords:
        sorted_countries = sorted(COUNTRY_COORDINATES.items(), key=lambda x: len(x[0]), reverse=True)
        for country_key, coords in sorted_countries:
            if (
                re.search(rf"\b{re.escape(country_key)}\b", lead_text)
                or country_key in url_tokens
                or (len(country_key) >= 4 and country_key.replace(" ", "") in clean_url)
            ):
                base_coords = coords
                break

    # 4. Check Phone Dialing Country Codes
    if not base_coords:
        if "+216" in lead_text or "216 " in lead_text or "(216)" in lead_text:
            base_coords = (36.8065, 10.1815)  # Tunisia
        elif "+33" in lead_text or "0033" in lead_text:
            base_coords = (48.8566, 2.3522)   # France
        elif "+212" in lead_text:
            base_coords = (33.5731, -7.5898)  # Morocco
        elif "+971" in lead_text:
            base_coords = (25.2048, 55.2708)  # UAE
        elif "+966" in lead_text:
            base_coords = (24.7136, 46.6753)  # Saudi Arabia

    # 5. Check Explicit Location string if provided
    if not base_coords and location and location.strip():
        loc_text = location.strip().lower()
        for city_key, coords in sorted(CITY_COORDINATES.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(rf"\b{re.escape(city_key)}\b", loc_text):
                base_coords = coords
                break
        if not base_coords:
            for country_key, coords in sorted(COUNTRY_COORDINATES.items(), key=lambda x: len(x[0]), reverse=True):
                if re.search(rf"\b{re.escape(country_key)}\b", loc_text):
                    base_coords = coords
                    break

    # 6. Fallback to Campaign Location if lead had zero geographic identifiers
    if not base_coords and fallback_location:
        fb_text = fallback_location.strip().lower()
        for city_key, coords in sorted(CITY_COORDINATES.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(rf"\b{re.escape(city_key)}\b", fb_text):
                base_coords = coords
                break
        if not base_coords:
            for country_key, coords in sorted(COUNTRY_COORDINATES.items(), key=lambda x: len(x[0]), reverse=True):
                if re.search(rf"\b{re.escape(country_key)}\b", fb_text):
                    base_coords = coords
                    break

    # 7. Default fallback anchor
    if not base_coords:
        base_coords = (36.8065, 10.1815)

    # 8. Apply deterministic spatial jitter (± 0.015 deg ~ 1.5 km)
    seed_str = f"{lead_id or ''}:{company_name or ''}:{website_url or ''}"
    hash_digest = hashlib.md5(seed_str.encode("utf-8")).hexdigest()

    lat_offset = ((int(hash_digest[:4], 16) % 1000) - 500) / 30000.0
    lon_offset = ((int(hash_digest[4:8], 16) % 1000) - 500) / 30000.0

    return round(base_coords[0] + lat_offset, 5), round(base_coords[1] + lon_offset, 5)
