from content_director import (
    AudienceSegment,
    CalendarCadence,
    CallToAction,
    ChannelPlan,
    ContentBrief,
    ContentFormat,
    ContentIntent,
    ContentMetricsTarget,
    ContentObjective,
    ContentPackage,
    ContentPiece,
    ContentPillar,
    ContentStatus,
    CTAType,
    EditorialCalendar,
    EditorialSlot,
    SEOBrief,
    assert_valid_content_package,
    validate_content_package,
)


def main() -> None:
    objective = ContentObjective(
        name="Generar confianza",
        intended_outcome="Aumentar consideración de soluciones de IA",
        metric="Tasa de guardados",
        target=">= 8%",
        horizon="30 días",
    )
    audience = AudienceSegment(
        name="Dueños de pequeñas empresas",
        description="Decisores que buscan reducir tiempo y riesgo",
        needs=("claridad", "casos reales"),
        pain_points=("falta de tiempo", "miedo a invertir mal"),
        preferred_channels=("TikTok",),
    )
    pillar = ContentPillar(
        name="IA práctica",
        purpose="Demostrar utilidad inmediata",
        themes=("automatización", "productividad"),
        formats=(ContentFormat.SHORT_VIDEO,),
    )
    channel = ChannelPlan(
        channel="TikTok",
        role="Descubrimiento y educación",
        audience_ids=(audience.audience_id,),
        preferred_formats=(ContentFormat.SHORT_VIDEO,),
        cadence=CalendarCadence.WEEKLY,
        publishing_frequency="3 piezas por semana",
        success_metrics=("retención", "guardados"),
    )
    piece = ContentPiece(
        title="3 tareas que un agente de IA puede ahorrar hoy",
        channel="TikTok",
        format=ContentFormat.SHORT_VIDEO,
        intent=ContentIntent.EDUCATION,
        pillar_id=pillar.pillar_id,
        audience_id=audience.audience_id,
        objective_id=objective.objective_id,
        hook="¿Cuántas horas pierdes cada semana en estas tareas?",
        key_message="La IA puede empezar con procesos pequeños y medibles.",
        outline=("Problema", "Tres ejemplos", "Siguiente paso"),
        cta=CallToAction("Guarda esta guía", CTAType.SAVE),
        metrics_target=ContentMetricsTarget("Tasa de guardados", ">= 8%", ("retención 3s",)),
        seo=SEOBrief("agentes de IA", ("IA para negocios",), "informacional", hashtags=("#IA", "#Negocios")),
        status=ContentStatus.SCHEDULED,
        publish_date="2026-08-03",
        source_references=("spkg_demo", "reporte_validado_001"),
    )
    calendar = EditorialCalendar(
        name="Calendario agosto",
        start_date="2026-08-01",
        end_date="2026-08-31",
        cadence=CalendarCadence.WEEKLY,
        slots=(EditorialSlot("2026-08-03", piece.piece_id, "TikTok"),),
    )
    package = ContentPackage(
        brief=ContentBrief(
            project_id="project_content_smoke",
            topic="Adopción de agentes de IA",
            business_objective="Generar oportunidades comerciales calificadas",
            value_proposition="Adopción simple, verificable y medible",
            positioning="Aliado confiable para pequeñas empresas",
            brand_voice=("claro", "confiable", "práctico"),
            source_strategy_package_id="spkg_demo",
            source_references=("reporte_validado_001",),
        ),
        objectives=(objective,),
        audiences=(audience,),
        pillars=(pillar,),
        channel_plans=(channel,),
        pieces=(piece,),
        calendar=calendar,
        source_references=("spkg_demo", "reporte_validado_001"),
    )

    issues = validate_content_package(package)
    assert not [issue for issue in issues if issue.severity == "error"], issues
    assert_valid_content_package(package)
    serialized = package.to_dict()
    assert serialized["package_id"].startswith("cpkg_")
    assert serialized["pieces"][0]["format"] == "short_video"
    assert package.piece_by_id(piece.piece_id) == piece
    assert len(package.pieces_for_channel("tiktok")) == 1

    print("OK: Dominio del Content Director operativo.")
    print("Package ID:", package.package_id)
    print("Schema:", package.schema_version)
    print("Objetivos:", len(package.objectives))
    print("Audiencias:", len(package.audiences))
    print("Pilares:", len(package.pillars))
    print("Canales:", len(package.channel_plans))
    print("Piezas:", len(package.pieces))
    print("Slots:", len(package.calendar.slots))
    print("Errores de validación:", len([i for i in issues if i.severity == "error"]))


if __name__ == "__main__":
    main()
