"""Borrador D-150 (IVA mensual). build_d150 calcula en Decimal preciso sobre el
resumen clasificación-aware (1B-5) de ventas (débito) y compras deducibles (crédito,
excluyendo tiquetes); d150_ovi produce la vista entera estilo OVI-Tribu."""
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.comprobante import Comprobante, LineaComprobante
from app.models.entrada_manual import EntradaManual
from app.motor.resumen import build_resumen

TIQUETE = "TiqueteElectronico"
_Q5 = Decimal("0.00001")   # escala de IVA (igual que Numeric(18,5))


def _add_tasa(por_tasa: dict, pct: str, base: Decimal, iva: Decimal) -> None:
    d = por_tasa.setdefault(pct, {"base": Decimal("0"), "iva": Decimal("0")})
    d["base"] += base
    d["iva"] += iva


def _colapsar(cats: dict) -> tuple[dict, Decimal, Decimal, Decimal]:
    """De {cat: {base, iva}} a (por_tasa, exentas, no_sujetas, no_deducibles).
    cat gravado = '{tipo} {pct}' → colapsa a '{pct}' sumando base+iva."""
    por_tasa: dict = {}
    exentas = Decimal("0"); no_sujetas = Decimal("0"); no_deducibles = Decimal("0")
    for cat, v in cats.items():
        if cat == "No Sujeto":
            no_sujetas += v["base"]
        elif cat == "No Deducibles":
            # No Deducibles: solo base; su IVA queda fuera del crédito (segregado, fiel al sistema viejo).
            no_deducibles += v["base"]
        elif cat.endswith("Exento"):
            exentas += v["base"]
        else:
            _add_tasa(por_tasa, cat.split(" ")[-1], v["base"], v["iva"])
    return por_tasa, exentas, no_sujetas, no_deducibles


def _aplicar_manual(e: EntradaManual, por_tasa: dict, exentas: Decimal, no_sujetas: Decimal,
                    no_deducibles: Decimal, es_compra: bool) -> tuple[Decimal, Decimal, Decimal]:
    """Suma una entrada manual a los acumuladores. Devuelve (exentas, no_sujetas, no_deducibles)."""
    if e.tarifa > 0:
        if es_compra and not e.deducible:
            no_deducibles += e.monto
        else:
            iva = (e.monto * e.tarifa / Decimal("100")).quantize(_Q5)
            pct = f"{int(e.tarifa)}%" if e.tarifa == e.tarifa.to_integral_value() else f"{e.tarifa.normalize()}%"
            _add_tasa(por_tasa, pct, e.monto, iva)
    elif e.no_sujeto:
        no_sujetas += e.monto
    else:
        exentas += e.monto
    return exentas, no_sujetas, no_deducibles


def _tiquetes_info(db: Session, cliente_id: int, periodo: str) -> tuple[int, Decimal]:
    row = db.execute(
        select(func.count(func.distinct(Comprobante.id)),
               func.coalesce(func.sum(LineaComprobante.iva_monto), Decimal("0")))
        .join(LineaComprobante, LineaComprobante.comprobante_id == Comprobante.id)
        .where(Comprobante.cliente_id == cliente_id, Comprobante.periodo == periodo,
               Comprobante.rol == "compra", Comprobante.tipo_doc == TIQUETE)
    ).one()
    return int(row[0]), row[1]


def _estado(neto: Decimal) -> str:
    if neto > 0:
        return "a_pagar"
    if neto < 0:
        return "saldo_favor"
    return "cero"


def _seccion(por_tasa: dict, exentas: Decimal, no_sujetas: Decimal, total_key: str,
             no_deducibles: Decimal | None = None,
             tiquetes: tuple[int, Decimal] | None = None) -> dict:
    por_tasa = {k: por_tasa[k] for k in sorted(por_tasa, key=lambda p: Decimal(p.rstrip("%")))}
    total_gravadas = sum((v["base"] for v in por_tasa.values()), Decimal("0"))
    total_iva = sum((v["iva"] for v in por_tasa.values()), Decimal("0"))
    sec = {
        "por_tasa": por_tasa,
        "exentas": exentas, "no_sujetas": no_sujetas,
        "total_gravadas": total_gravadas,
        total_key: total_iva,
        "total_general": total_gravadas + exentas + no_sujetas,
    }
    if no_deducibles is not None:
        n, iva_tiq = tiquetes if tiquetes is not None else (0, Decimal("0"))
        sec["no_deducibles"] = no_deducibles
        sec["tiquetes_excluidos_n"] = n
        sec["tiquetes_excluidos_iva"] = iva_tiq
    return sec


def build_d150(db: Session, cliente_id: int, periodo: str) -> dict:
    """Estructura PRECISA (Decimal) del borrador D-150 del cliente/período."""
    manuales = list(db.scalars(select(EntradaManual).where(
        EntradaManual.cliente_id == cliente_id, EntradaManual.periodo == periodo)))

    # Ventas → débito
    v_por_tasa, v_exentas, v_no_sujetas, _ = _colapsar(
        build_resumen(db, cliente_id, periodo, "venta"))
    for e in (m for m in manuales if m.rol == "venta"):
        v_exentas, v_no_sujetas, _nd = _aplicar_manual(
            e, v_por_tasa, v_exentas, v_no_sujetas, Decimal("0"), es_compra=False)
    ventas = _seccion(v_por_tasa, v_exentas, v_no_sujetas, "total_impuesto")

    # Compras → crédito (sin tiquetes; No Deducibles/No Sujeto fuera del crédito)
    c_por_tasa, c_exentas, c_no_sujetas, c_no_deducibles = _colapsar(
        build_resumen(db, cliente_id, periodo, "compra", excluir_tipos={TIQUETE}))
    for e in (m for m in manuales if m.rol == "compra"):
        c_exentas, c_no_sujetas, c_no_deducibles = _aplicar_manual(
            e, c_por_tasa, c_exentas, c_no_sujetas, c_no_deducibles, es_compra=True)
    compras = _seccion(c_por_tasa, c_exentas, c_no_sujetas, "total_credito",
                       no_deducibles=c_no_deducibles,
                       tiquetes=_tiquetes_info(db, cliente_id, periodo))

    debito = ventas["total_impuesto"]
    credito = compras["total_credito"]
    neto = debito - credito
    liquidacion = {"debito_fiscal": debito, "credito_fiscal": credito,
                   "impuesto_neto": neto, "estado": _estado(neto)}
    return {"ventas": ventas, "compras": compras, "liquidacion": liquidacion}


def _ri(x: Decimal) -> int:
    return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _seccion_ovi(sec: dict, total_key: str) -> dict:
    por_tasa = {}
    for pct, v in sec["por_tasa"].items():
        rate = Decimal(pct.rstrip("%")) / Decimal("100")
        por_tasa[pct] = {"base": _ri(v["base"]), "iva": _ri(v["base"] * rate)}
    total_gravadas = sum((t["base"] for t in por_tasa.values()), 0)
    total_iva = sum((t["iva"] for t in por_tasa.values()), 0)
    exentas = _ri(sec["exentas"]); no_sujetas = _ri(sec["no_sujetas"])
    out = {
        "por_tasa": por_tasa, "exentas": exentas, "no_sujetas": no_sujetas,
        "total_gravadas": total_gravadas, total_key: total_iva,
        "total_general": total_gravadas + exentas + no_sujetas,
    }
    if "no_deducibles" in sec:
        out["no_deducibles"] = _ri(sec["no_deducibles"])
        out["tiquetes_excluidos_n"] = sec["tiquetes_excluidos_n"]
        out["tiquetes_excluidos_iva"] = _ri(sec["tiquetes_excluidos_iva"])
    return out


def jsonify_preciso(x):
    """Serializa la estructura precisa para JSON: Decimal→str, recursivo en dicts."""
    if isinstance(x, Decimal):
        return str(x)
    if isinstance(x, dict):
        return {k: jsonify_preciso(v) for k, v in x.items()}
    return x


def d150_ovi(preciso: dict) -> dict:
    """Vista entera estilo OVI-Tribu: base→entero, iva=round(base×tasa), totales=suma de redondeados."""
    ventas = _seccion_ovi(preciso["ventas"], "total_impuesto")
    compras = _seccion_ovi(preciso["compras"], "total_credito")
    debito = ventas["total_impuesto"]; credito = compras["total_credito"]
    neto = debito - credito
    return {"ventas": ventas, "compras": compras,
            "liquidacion": {"debito_fiscal": debito, "credito_fiscal": credito,
                            "impuesto_neto": neto, "estado": _estado(neto)}}
