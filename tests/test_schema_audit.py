"""Tests unitaires de l'analyse de schéma."""

from app.schema_audit import (
    EXPECTED_ANNONCE_COLUMNS,
    ColumnInfo,
    compare_expected_schema,
)


def _expected_columns() -> list[ColumnInfo]:
    return [
        ColumnInfo(
            name=name,
            data_type=data_type,
            nullable=name
            not in {"id", "premiere_collecte", "derniere_maj"},
            position=position,
        )
        for position, (name, data_type) in enumerate(
            EXPECTED_ANNONCE_COLUMNS.items(),
            start=1,
        )
    ]


def test_expected_schema_has_no_missing_or_type_mismatch() -> None:
    comparison = compare_expected_schema(_expected_columns())

    assert comparison["missing_columns"] == []
    assert comparison["unexpected_columns"] == []
    assert comparison["type_mismatches"] == []
    assert any(
        "TIMESTAMPTZ" in recommendation
        for recommendation in comparison["recommendations"]
    )


def test_schema_difference_is_reported() -> None:
    columns = [
        column
        for column in _expected_columns()
        if column.name != "id"
    ]
    columns[0] = ColumnInfo(
        name=columns[0].name,
        data_type="integer",
        nullable=True,
        position=columns[0].position,
    )

    comparison = compare_expected_schema(columns)

    assert comparison["missing_columns"] == ["id"]
    assert comparison["type_mismatches"][0]["column"] == "groupe_nom"
