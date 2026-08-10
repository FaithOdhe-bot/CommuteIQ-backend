"""
CommuteIQ — Transport Restriction Database
Compiled from official government sources and verified news reports
Last updated: August 2026

Sources:
- Lagos State Government ban notice (Feb 2020, enforced 2022)
- FCTA ban announcement (August 2026, FCT Minister Wike)
- Kano State Police Command statement (Dec 2025)
- Rivers State ban (2008, Amaechi administration)
- Nairobi County gazette notice (Jan 2018, updated 2022/2025)
- MOJA Expressway statement (Feb 2026)
- Nairobi City County Boda Boda Regulations 2025
- Oyo State Executive Order (Jun 2026)
- NigeriaInfo/Legit.ng multi-city ban reports
"""

TRANSPORT_RESTRICTIONS = {

    # ════════════════════════════════════════════════════════
    # NIGERIA
    # ════════════════════════════════════════════════════════

    "nigeria": {

        "okada": {

            "lagos": {
                # Banned from 6 LGAs, 9 LCDAs, 10 major highways, 40 bridges
                # LGAs: Lagos Island, Lagos Mainland, Eti-Osa, Apapa, Ikeja, Surulere
                # Effective: February 1 2020, re-enforced 2022 and ongoing
                "status":          "BANNED",
                "max_direct_km":   5.0,
                "restricted_lgas": [
                    "Lagos Island", "Lagos Mainland", "Eti-Osa",
                    "Apapa", "Ikeja", "Surulere",
                ],
                "restricted_roads": [
                    "Ikorodu Road", "Third Mainland Bridge", "Carter Bridge",
                    "Lagos-Ibadan Expressway", "Apapa-Oshodi Expressway",
                    "Coastal Road", "Falomo", "Marina", "Ajah Roundabout",
                    "Ogombo", "Abraham Adesanya Junction",
                ],
                "legal_alt":       "brt",
                "legal_alt_label": "BRT Bus",
                "courier_allowed": True,   # Delivery/dispatch bikes still allowed
                "message": (
                    "⚠️ Okadas are banned in Lagos Island, Ikeja, Surulere, Apapa, "
                    "Eti-Osa and on all major highways. For a {dist:.0f}km route the "
                    "legal option is: 🛵 Okada for short inner-street legs only → "
                    "🚍 BRT or 🚌 Danfo for the highway section. "
                    "Estimated combined fare: ₦500–₦1,600. Only courier/dispatch bikes "
                    "are legally allowed on restricted roads."
                ),
            },

            "abuja": {
                # Phase 1 Central City Districts ban — Aug 2026
                # Includes CBD, Maitama, Asokoro, Wuse, Garki
                # Security rationale: links to bandit activity + traffic management
                "status":          "BANNED_CITY_CENTRE",
                "max_direct_km":   6.0,
                "restricted_areas": [
                    "Central Business District", "Maitama", "Asokoro",
                    "Wuse", "Garki",
                ],
                "restricted_roads": [
                    "Shehu Shagari Way", "Ahmadu Bello Way",
                    "Yakubu Gowon Way", "Ring Road 1", "Central Expressway",
                ],
                "legal_alt":       "rideshare",
                "legal_alt_label": "Ride Share (Bolt/Uber)",
                "courier_allowed": True,
                "message": (
                    "⚠️ Okadas and keke napep are banned in Abuja Phase 1 districts "
                    "(CBD, Maitama, Asokoro, Wuse, Garki) by FCTA order, August 2026. "
                    "Use 🚖 Bolt/Uber or the Abuja Metro Light Rail instead. "
                    "Also available: 'along-along' shared taxis from Berger Roundabout, "
                    "Area 1 Bridge, and Airport Road junctions."
                ),
            },

            "kano": {
                # Statewide ban enforced by Kano State Police (confirmed Dec 2025)
                # Keke also restricted 10pm-6am
                "status":          "BANNED_STATEWIDE",
                "max_direct_km":   0,    # banned everywhere
                "legal_alt":       "rideshare",
                "legal_alt_label": "Taxi / Ride Share",
                "courier_allowed": True,
                "message": (
                    "⚠️ Commercial motorcycles (okada) are fully banned in Kano "
                    "State (Kano State Police, Dec 2025). Use 🚖 Taxi or Ride Share. "
                    "Delivery/courier bikes remain allowed."
                ),
            },

            "port harcourt": {
                # Banned since 2008 under Amaechi; Obio/Akpor LGA extending ban Aug 2026
                "status":          "BANNED",
                "max_direct_km":   4.0,
                "restricted_areas": [
                    "Port Harcourt City", "Obio/Akpor LGA (from Aug 2026)",
                ],
                "legal_alt":       "rideshare",
                "legal_alt_label": "Taxi / Ride Share",
                "courier_allowed": True,
                "message": (
                    "⚠️ Okadas have been banned in Port Harcourt since 2008. "
                    "Obio/Akpor LGA extended the ban in August 2026. "
                    "Use 🚖 Taxi or Ride Share for this {dist:.0f}km trip."
                ),
            },

            "enugu": {
                # Banned since 2011
                "status":          "BANNED",
                "max_direct_km":   3.0,
                "legal_alt":       "keke",
                "legal_alt_label": "Keke Napep",
                "courier_allowed": True,
                "message": (
                    "⚠️ Okadas are banned in Enugu (ban since 2011). "
                    "Use 🛺 Keke Napep or 🚖 Taxi for a {dist:.0f}km trip."
                ),
            },

            "asaba": {
                # Delta State okada ban — entire Asaba Capital Territory
                # Enforced by DESTMA + Nigeria Police Force Task Force
                # Primary modes now: Keke Napep + Town Buses
                "status":          "BANNED",
                "max_direct_km":   0,
                "restricted_areas": ["Asaba Capital Territory"],
                "legal_alt":       "keke",
                "legal_alt_label": "Keke Napep",
                "courier_allowed": True,
                "message": (
                    "⚠️ Okadas are fully banned in Asaba Capital Territory "
                    "(Delta State Government ban, enforced by DESTMA). "
                    "Use 🛺 Keke Napep for short trips or 🚌 Town Bus for "
                    "medium distances (Okpanam, Ibusa, Koka routes)."
                ),
            },

            "benin city": {
                # Banned in core LGAs: Oredo, Egor, Ikpoba Okha
                # Also restricted in selected Ovia North-East and Uhunmwonde corridors
                # Enforced by EDSTMA
                "status":          "BANNED",
                "max_direct_km":   4.0,
                "restricted_areas": [
                    "Oredo LGA", "Egor LGA", "Ikpoba Okha LGA",
                    "Ring Road", "King's Square",
                ],
                "legal_alt":       "keke",
                "legal_alt_label": "Keke Napep",
                "courier_allowed": True,
                "message": (
                    "⚠️ Okadas are banned in Benin City core LGAs (Oredo, Egor, "
                    "Ikpoba Okha) enforced by EDSTMA. "
                    "Use 🛺 Keke Napep or 🚌 Danfo/Taxi. "
                    "ECTS government buses operate on Ugbowo, Airport Road, "
                    "and Sapele Road corridors at regulated fares."
                ),
            },

            "ibadan": {
                # Night curfew 10:30pm-5:30am (Oyo State Executive Order Jun 2026)
                "status":          "NIGHT_CURFEW",
                "curfew_start":    "22:30",
                "curfew_end":      "05:30",
                "max_direct_km":   15.0,
                "legal_alt":       "keke",
                "legal_alt_label": "Keke Napep",
                "courier_allowed": True,
                "message": (
                    "⚠️ Oyo State has banned okadas between 10:30 PM and 5:30 AM "
                    "(Executive Order, June 2026). If travelling at night, use "
                    "🛺 Keke Napep or 🚖 Taxi instead."
                ),
            },
        },

        "keke": {

            "lagos": {
                # Keke banned alongside okada on same restricted roads
                "status":          "BANNED_MAJOR_ROADS",
                "max_direct_km":   8.0,
                "restricted_roads": [
                    "major highways", "bridges", "flyovers",
                    "Lagos Island", "Apapa", "Ikeja main roads",
                ],
                "legal_alt":       "danfo",
                "legal_alt_label": "Danfo",
                "message": (
                    "⚠️ Tricycles (keke napep) are banned on major Lagos highways, "
                    "bridges, and in Apapa and Lagos Island. For a {dist:.0f}km trip "
                    "use 🚌 Danfo or 🚍 BRT instead."
                ),
            },

            "abuja": {
                # Banned alongside okada in city centre (August 2026)
                "status":          "BANNED_CITY_CENTRE",
                "max_direct_km":   6.0,
                "legal_alt":       "rideshare",
                "legal_alt_label": "Ride Share",
                "message": (
                    "⚠️ Keke napep is banned in Abuja city centre "
                    "(FCTA order, August 2026). Use 🚖 Bolt/Uber instead."
                ),
            },

            "kano": {
                # Night restriction 10pm-6am
                "status":          "NIGHT_CURFEW",
                "curfew_start":    "22:00",
                "curfew_end":      "06:00",
                "max_direct_km":   20.0,
                "legal_alt":       "rideshare",
                "message": (
                    "⚠️ Keke napep is restricted in Kano between 10:00 PM and 6:00 AM. "
                    "Use 🚖 Taxi or Ride Share for night travel."
                ),
            },
        },
    },

    # ════════════════════════════════════════════════════════
    # KENYA
    # ════════════════════════════════════════════════════════

    "kenya": {

        "boda_boda": {

            "nairobi": {
                # CBD ban enforced by Nairobi County (ongoing since 2018)
                # Nairobi Expressway fully banned (MOJA Expressway, Feb 2026)
                # Nairobi City County Boda Boda Regulations 2025 — designated zones
                "status":          "PARTIAL_BAN",
                "max_direct_km":   12.0,
                "restricted_areas": [
                    "CBD (Central Business District)",
                    "Nairobi Expressway (Mlolongo–James Gichuru Road)",
                ],
                "restricted_roads": [
                    "Nairobi Expressway",
                    "CBD streets (Tom Mboya, Moi Avenue, Kenyatta Avenue, Harambee Ave)",
                ],
                "permitted_cbd_roads": [
                    "Kirinyaga Road", "University Way",
                    "Uhuru Highway", "Haile Selassie Avenue", "Racecourse Road",
                ],
                "legal_alt":       "matatu",
                "legal_alt_label": "Matatu",
                "courier_allowed": True,
                "message": (
                    "⚠️ Boda bodas are banned in Nairobi CBD and on the Nairobi Expressway "
                    "(Nairobi County regulations, 2025). For a {dist:.0f}km CBD-bound trip "
                    "use 🚐 Matatu and walk the last leg, or take a 🚕 Taxi. "
                    "Permitted CBD approach roads: Kirinyaga Rd, University Way, Uhuru Hwy."
                ),
            },
        },

        "matatu": {

            "nairobi": {
                # Matatus banned from entering CBD — must use designated termini
                # Ongoing legal battle (High Court gave relief Dec 2025 for some SACCOs)
                # Nairobi County gazetted 89 new routes (Dec 2024)
                "status":          "TERMINUS_RESTRICTION",
                "max_direct_km":   None,   # distance not the issue — it's CBD access
                "restricted_areas": ["CBD — matatus must use designated termini"],
                "designated_termini": {
                    "Thika Road / Kiambu Road / Ruiru": "Murang'a Road (Fig Tree) Terminus B",
                    "Waiyaki Way / Uhuru Hwy / Limuru Rd": "Murang'a Road (Fig Tree) Terminus A",
                    "Jogoo Road / Lusaka Road": "Muthurwa Terminus",
                    "Mombasa Road / Lang'ata Road": "Hakati Terminus",
                    "Ngong Road": "Railways Terminus",
                    "Juja Rd / Ring Rd Ngara / Park Rd": "Ngara Road Terminus",
                },
                "message": (
                    "ℹ️ Matatus do not enter Nairobi CBD — they stop at designated termini "
                    "on the outskirts. From there you walk or take a boda boda "
                    "(on permitted roads only) to your final CBD destination. "
                    "Thika Rd buses → Fig Tree B | Waiyaki Way → Fig Tree A | "
                    "Mombasa Rd → Hakati | Ngong Rd → Railways Terminus."
                ),
            },
        },
    },
}


def get_restriction(mode: str, city: str, country: str) -> dict | None:
    """
    Returns restriction data for a mode/city combination, or None if unrestricted.
    """
    return (
        TRANSPORT_RESTRICTIONS
        .get(country, {})
        .get(mode.lower(), {})
        .get(city.lower())
    )
