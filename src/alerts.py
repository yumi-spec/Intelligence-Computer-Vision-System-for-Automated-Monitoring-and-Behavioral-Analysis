from __future__ import annotations

OBS, DIAG, ACT = "Nakita", "Posibleng Sanhi", "Dapat Gawin"

DISCLAIMER = "Pagtataya lamang ito batay sa galaw ng isda sa video. Hindi pa ito kumpirmado."

LEVEL_TEXT = {
    "critical": "Suriin agad",
    "warning": "Bantayan",
    "ok": "Maayos"
}

KIND_LABEL = {
    "fish_unusual": "Hindi normal na paglangoy",
    "fish_motionless": "Hindi gumagalaw",
    "school_left": "Nahiwalay sa grupo",
    "school_turn": "Biglaang pagliko ng grupo",
    "disturbance": "Biglaang pagbabago ng galaw",
    "unusual": "Maraming isda ang hindi normal ang paglangoy",
    "no_fish": "Walang nakitang isda",
    "erratic": "Hindi normal na paggalaw",
    "low_oxygen": "Posibleng mababang oxygen",
}

LEVELS = {"fish_motionless": "critical"}

_CHECK_WATER = "Suriin ang kalidad ng tubig (oxygen, temperatura, pH, at ammonia)"


def _unusual(c: dict) -> dict:
    f = c.get("fish", "?")

    obs = {
        "A": f"Ang Isda {f} ay paulit-ulit na nagpapalit ng direksyon at naiiba ang paglangoy kumpara sa ibang isda.",
        "B": f"Nagbago ang paraan ng paglangoy ng Isda {f} kumpara sa dati nitong paglangoy.",
        "C": f"Kapansin-pansing bumagal o huminto ang paggalaw ng Isda {f} kumpara sa dati nitong galaw."
    }.get(c.get("why", "A"))

    return {
        "title": f"Hindi normal ang paglangoy ng Isda {f}",
        "observation": obs,
        "diagnosis": "Posibleng nakararanas ng stress, natatakot, o may sakit ang isda.",
        "action": f"Obserbahan ang Isda {f} sa palaisdaan. {_CHECK_WATER} at tingnan kung may nakakagambala sa paligid."
    }


def _motionless(c: dict) -> dict:
    f, s = c.get("fish", "?"), c.get("secs", 6)

    return {
        "title": f"Hindi gumagalaw ang Isda {f}",
        "observation": f"Hindi gumalaw ang Isda {f} sa loob ng {s} segundo o higit pa.",
        "diagnosis": (
            "Posibleng may sakit, nanghihina, o patay na ang isda. "
            "Posible ring nagpapahinga lamang ito o nagkamali ang sistema sa pagkilala "
            "(halimbawa, bato o ibang bagay na napagkamalang isda)."
        ),
        "action": (
            f"Suriin agad ang Isda {f} sa palaisdaan. "
            "Kung talagang hindi ito gumagalaw, humingi ng tulong sa responsableng tauhan "
            "at suriin ang kalidad ng tubig at oxygen."
        )
    }


def _disturbance(c: dict) -> dict:
    parts = [
        f"{c[k]} ang {w}"
        for k, w in (
            ("turn", "pagliko"),
            ("fast", "pagbilis"),
            ("stop", "paghinto")
        )
        if c.get(k)
    ]

    extra = f" {', '.join(parts)}." if parts else ""

    return {
        "title": "Biglaang nagbago ang paglangoy ng mga isda",
        "observation": (
            f"Sa loob lamang ng ilang segundo, nagbago ang paglangoy "
            f"ng {c.get('k', '?')} sa {c.get('n', '?')} na isda.{extra}"
        ),
        "diagnosis": (
            "Posibleng nagulat o natakot ang mga isda dahil sa kaguluhan sa paligid, "
            "tulad ng presensya ng tao, ingay, anino, o pagbabago sa tubig."
        ),
        "action": (
            "Suriin kung may nagbago sa paligid ng palaisdaan. "
            "Suriin din ang oxygen at temperatura ng tubig, at patuloy na obserbahan ang mga isda."
        )
    }


def _school_turn(c: dict) -> dict:
    return {
        "title": "Biglang lumiko ang grupo ng mga isda",
        "observation": (
            f"Ang {c.get('k', '?')} na isda ay magkakasamang lumalangoy "
            f"sa iisang direksyon ngunit bigla silang lumiko nang humigit-kumulang "
            f"{c.get('deg', '?')} degrees."
        ),
        "diagnosis": (
            "Posibleng may iniwasan o ikinatakot ang grupo, "
            "tulad ng tao, anino, o sagabal."
        ),
        "action": (
            "Suriin kung may tao o bagay na maaaring nakagulat sa grupo. "
            "Obserbahan kung mauulit ang ganitong paggalaw."
        )
    }


def _school_left(c: dict) -> dict:
    f = c.get("fish", "?")

    return {
        "title": f"Nahiwalay sa grupo ang Isda {f}",
        "observation": (
            f"Dating lumalangoy kasama ng grupo ang Isda {f}, "
            "ngunit ngayon ay nahiwalay na ito at lumalayo sa mga kasamahan nito."
        ),
        "diagnosis": "Posibleng nanghihina, may sakit, o natatakot ang isda.",
        "action": (
            f"Obserbahan ang Isda {f}. Kung patuloy itong naihihiwalay sa grupo, "
            "ipasuri ito sa responsableng tauhan at suriin ang kalidad ng tubig."
        )
    }


def _school_unusual(c: dict) -> dict:
    return {
        "title": "Maraming isda ang hindi normal ang paglangoy",
        "observation": (
            f"{c.get('u', '?')} sa {c.get('cl', '?')} na isda "
            f"({c.get('pct', '?')}%) ang nagpapakita ng hindi normal na paglangoy "
            "kumpara sa grupo o sa dati nilang paggalaw."
        ),
        "diagnosis": (
            "Posibleng may problema sa kalidad ng tubig o sa kapaligiran, "
            "tulad ng mababang oxygen o kaguluhan sa paligid."
        ),
        "action": (
            "Suriin agad ang oxygen, temperatura, pH, at ammonia ng tubig. "
            "Obserbahan din ang mga isda at ang kanilang kapaligiran."
        )
    }


def _no_fish(c: dict) -> dict:
    return {
        "title": "Walang nakitang isda",
        "observation": "Walang nakitang isda sa video.",
        "diagnosis": (
            "Posibleng malabo ang tubig, madilim ang video, "
            "o hindi nakapuwesto nang maayos ang camera."
        ),
        "action": (
            "Suriin ang camera at ang video. "
            "Tiyaking malinaw na nakikita ang bahagi ng palaisdaan."
        )
    }


_BUILDERS = {
    "fish_unusual": _unusual,
    "fish_motionless": _motionless,
    "disturbance": _disturbance,
    "school_turn": _school_turn,
    "school_left": _school_left,
    "school_unusual": _school_unusual,
    "no_fish": _no_fish
}


def build(kind: str, ctx: dict | None = None) -> dict:
    """title / observation / diagnosis / action / level para sa isang alerto."""
    d = _BUILDERS[kind](ctx or {})
    d["level"] = LEVELS.get(kind, "warning")
    return d


def for_snapshot(snap):
    """Teksto ng alerto para sa resulta ng buong grupo."""
    kind = getattr(snap, "kind", "")

    if kind == "no_fish":
        return build("no_fish")

    if kind == "unusual":
        u = int(getattr(snap, "unusual", 0))
        cl = (
            u
            + int(getattr(snap, "normal", 0))
            + int(getattr(snap, "schooling", 0))
            + int(getattr(snap, "feeding", 0))
        )

        return build(
            "school_unusual",
            {
                "u": u,
                "cl": cl,
                "pct": round(100 * u / cl) if cl else 0
            }
        )

    return None


def recommendation(classified: int, unusual: int) -> dict:
    """Teksto para sa Recommendation panel sa dashboard."""

    if classified == 0:
        return {
            "tone": "mut",
            "badge": "Naghihintay",
            "headline": "Kinokolekta pa ang datos",
            "note": (
                "Kailangang obserbahan ang bawat isda sa loob ng ilang segundo "
                "bago matukoy ang paraan ng paglangoy nito."
            )
        }

    if unusual > 0:
        return {
            "tone": "warn",
            "badge": LEVEL_TEXT["warning"],
            "headline": f"{unusual} sa {classified} na isda ang hindi normal ang paglangoy",
            "observation": (
                "May nakitang hindi normal na direksyon o galaw sa ilan sa mga isda."
            ),
            "diagnosis": (
                "Posibleng nakararanas ng stress, natatakot, o may sakit ang mga isda, "
                "o kaya ay may problema sa kalidad ng tubig."
            ),
            "action": (
                "Obserbahan ang mga isda at suriin ang oxygen, temperatura, "
                "pH, at ammonia ng tubig."
            )
        }

    return {
        "tone": "ok",
        "badge": LEVEL_TEXT["ok"],
        "headline": "Ipagpatuloy ang regular na pagmamanman",
        "note": "Walang nakitang hindi normal na paglangoy."
    }
