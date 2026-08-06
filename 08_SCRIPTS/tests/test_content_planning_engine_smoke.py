from content_director import ContentPlanningEngine, PlanningConfig


def strategy_fixture() -> dict:
    return {
        "project_id": "project_content_planning",
        "topic": "Adopción de agentes de IA en pequeñas empresas mexicanas",
        "business_objective": "Generar confianza y oportunidades comerciales medibles",
        "value_proposition": "Adopción práctica, verificable y de bajo riesgo",
        "positioning": "Guía confiable para implementar IA sin complejidad innecesaria",
        "objectives": [
            {"name": "Autoridad", "outcome": "Aumentar confianza", "metric": "leads cualificados", "target": "30", "horizon": "90 días"},
            {"name": "Educación", "outcome": "Reducir incertidumbre", "metric": "guardados", "target": "500", "horizon": "90 días"},
        ],
        "audiences": [{
            "name": "Dueños de pequeñas empresas",
            "description": "Decisores con poco tiempo y alto cuidado del presupuesto",
            "needs": ["ahorrar tiempo", "reducir riesgo"],
            "barriers": ["costo", "complejidad"],
        }],
        "content_pillars": [
            {"name": "Educación", "purpose": "Explicar conceptos", "themes": ["automatización", "casos"], "formats": ["carrusel", "short"]},
            {"name": "Confianza", "purpose": "Demostrar resultados", "themes": ["evidencia", "testimonios"], "formats": ["artículo"]},
            {"name": "Implementación", "purpose": "Guiar acciones", "themes": ["pasos", "herramientas"], "formats": ["guía"]},
        ],
        "channels": ["TikTok", "YouTube", "Blog"],
        "kpis": [{"name": "Leads cualificados"}, {"name": "Retención de video"}],
        "roadmap": [{"phase": "Validación", "horizon": "0-30 días"}, {"phase": "Escala", "horizon": "31-90 días"}],
        "risks": ["Prometer beneficios sin evidencia"],
        "assumptions": ["La audiencia tiene acceso a internet"],
        "source_references": ["reporte_validado_001", "entrevistas_2026"],
        "package_id": "spkg_fixture_001",
    }


def main() -> None:
    engine = ContentPlanningEngine(PlanningConfig(
        horizon_weeks=12,
        pieces_per_week=3,
        start_date="2026-08-03",
    ))
    result = engine.build(strategy_fixture())
    plan = result.plan
    assert plan.plan_id.startswith("cplan_")
    assert plan.brief.source_strategy_package_id == "spkg_fixture_001"
    assert len(plan.objectives) == 2
    assert len(plan.audiences) == 1
    assert len(plan.pillars) == 3
    assert len(plan.channel_plans) == 3
    assert sum(item.percentage for item in plan.allocations) == 100
    assert plan.editorial_policy.target_piece_count == 36
    assert result.score.overall >= 9.0
    serialized = result.to_dict()
    assert serialized["plan"]["editorial_policy"]["target_piece_count"] == 36

    print("OK: Content Planning Engine operativo.")
    print("Plan ID:", plan.plan_id)
    print("Strategy Package:", plan.brief.source_strategy_package_id)
    print("Objetivos:", len(plan.objectives))
    print("Audiencias:", len(plan.audiences))
    print("Pilares:", len(plan.pillars))
    print("Canales:", len(plan.channel_plans))
    print("Horizonte:", plan.editorial_policy.total_weeks, "semanas")
    print("Piezas objetivo:", plan.editorial_policy.target_piece_count)
    print("Asignación total:", sum(item.percentage for item in plan.allocations))
    print("Score:", result.score.overall)


if __name__ == "__main__":
    main()
