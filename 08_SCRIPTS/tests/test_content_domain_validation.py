from content_director import (
    CalendarCadence,
    ContentBrief,
    ContentPackage,
    EditorialCalendar,
    validate_content_package,
)


def main() -> None:
    package = ContentPackage(
        brief=ContentBrief(
            project_id="",
            topic="",
            business_objective="Prueba negativa",
            value_proposition="",
            positioning="",
            brand_voice=(),
        ),
        objectives=(),
        audiences=(),
        pillars=(),
        channel_plans=(),
        pieces=(),
        calendar=EditorialCalendar(
            name="Vacío",
            start_date="2026-08-01",
            end_date="2026-08-31",
            cadence=CalendarCadence.MONTHLY,
            slots=(),
        ),
    )
    issues = validate_content_package(package)
    codes = {issue.code for issue in issues}
    assert "brief.project_id.required" in codes
    assert "brief.topic.required" in codes
    assert "pieces.required" in codes
    assert len(issues) >= 7
    print("OK: Validadores del dominio detectan paquetes incompletos.")
    print("Problemas detectados:", len(issues))


if __name__ == "__main__":
    main()
