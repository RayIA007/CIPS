from content_director import ContentPlanningEngine, ContentPlanningError, PlanningConfig


def main() -> None:
    engine = ContentPlanningEngine(PlanningConfig(start_date="2026-08-03"))
    incomplete = {
        "project_id": "project_invalid",
        "topic": "Tema incompleto",
        "business_objective": "Objetivo",
        "objectives": [],
        "audiences": [],
        "content_pillars": [],
    }
    try:
        engine.build(incomplete)
    except ContentPlanningError as exc:
        message = str(exc)
        assert "objectives" in message
        assert "audiences" in message
        assert "content_pillars" in message
        print("OK: Planning Engine rechaza StrategyPackage incompleto.")
        print("Diagnóstico:", message)
        return
    raise AssertionError("Se esperaba ContentPlanningError")


if __name__ == "__main__":
    main()
