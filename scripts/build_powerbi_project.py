"""
Step 6 - VISUALIZE: generate a Power BI Project (.pbip) for the pipeline output.

Creates powerbi/Shop_Dashboard.pbip with
  - a semantic model (TMDL): fct_orders, dim_customer, dim_product, mart_daily_revenue,
    relationships (star schema) and DAX measures
  - a report (PBIR) with a ready-made dashboard page

The data source is a parameter (DataUrl). By default it points to the CSV files
in this GitHub repository, so the report works on any computer and can also be
refreshed in the Power BI Service (cloud). Change the parameter to a local
folder or warehouse if needed.

Open powerbi/Shop_Dashboard.pbip in Power BI Desktop (Windows).
"""
import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi"
NAME = "Shop_Dashboard"
SM = OUT / f"{NAME}.SemanticModel"
RP = OUT / f"{NAME}.Report"
DATA_URL = "https://raw.githubusercontent.com/Dhrukumar23/shop-data-pipeline/main/output/"
THEME_SRC = Path(__file__).resolve().parent / "powerbi_assets" / "Fluent2-CY26SU09.json"


def gid():
    return uuid.uuid4().hex[:20]


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def wjson(path: Path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- semantic model
TABLES = {
    "fct_orders": [
        ("order_id", "string"), ("order_date", "dateTime"), ("customer_id", "string"),
        ("product_id", "string"), ("country", "string"), ("category", "string"),
        ("status", "string"), ("quantity", "int64"), ("gross_amount", "double"),
        ("paid_amount", "double"), ("refund_amount", "double"), ("net_revenue", "double"),
        ("is_fully_paid", "boolean"),
    ],
    "dim_customer": [
        ("customer_id", "string"), ("customer_name", "string"), ("email", "string"),
        ("country", "string"), ("first_order_date", "dateTime"), ("lifetime_orders", "int64"),
    ],
    "dim_product": [
        ("product_id", "string"), ("product_name", "string"), ("category", "string"),
        ("list_price", "double"),
    ],
    "mart_daily_revenue": [
        ("order_date", "dateTime"), ("country", "string"), ("orders", "int64"),
        ("customers", "int64"), ("gross_amount", "double"), ("refunds", "double"),
        ("net_revenue", "double"), ("cancel_rate", "double"), ("unpaid_rate", "double"),
    ],
}
M_TYPES = {"string": "type text", "dateTime": "type date", "int64": "Int64.Type",
           "double": "type number", "boolean": "type logical"}

EURO = "\\€#,0;-\\€#,0;\\€#,0"
MEASURES = [
    ("Net Revenue", "SUM(fct_orders[net_revenue])", EURO),
    ("Gross Sales", "SUM(fct_orders[gross_amount])", EURO),
    ("Refunds", "SUM(fct_orders[refund_amount])", EURO),
    ("Orders", "COUNTROWS(fct_orders)", "#,0"),
    ("Customers", "DISTINCTCOUNT(fct_orders[customer_id])", "#,0"),
    ("Avg Order Value", "DIVIDE([Gross Sales], [Orders])", "\\€#,0.00"),
    ("Cancel Rate", 'DIVIDE(CALCULATE([Orders], fct_orders[status] = "cancelled"), [Orders])', "0.0%"),
    ("Refund Rate", "DIVIDE([Refunds], [Gross Sales])", "0.0%"),
]


def table_tmdl(name, cols, measures=()):
    lines = [f"table {name}", f"\tlineageTag: {uuid.uuid4()}", ""]
    for mname, expr, fmt in measures:
        lines += [f"\tmeasure '{mname}' = {expr}", f"\t\tformatString: {fmt}",
                  f"\t\tlineageTag: {uuid.uuid4()}", ""]
    for c, t in cols:
        lines += [f"\tcolumn {c}", f"\t\tdataType: {t}"]
        if t == "dateTime":
            lines.append("\t\tformatString: Short Date")
        if t in ("int64", "double") and not c.endswith("_id"):
            lines.append("\t\tsummarizeBy: sum")
        else:
            lines.append("\t\tsummarizeBy: none")
        lines += [f"\t\tsourceColumn: {c}", f"\t\tlineageTag: {uuid.uuid4()}", ""]
    types = ", ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, t in cols)
    lines += [
        f"\tpartition {name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(Web.Contents(DataUrl & "{name}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(lines)


def build_model():
    wjson(SM / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid4())}})
    wjson(SM / "definition.pbism", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    d = SM / "definition"
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    write(d / "model.tmdl", "\n".join([
        "model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
        "\tannotation PBI_QueryOrder = [\"DataUrl\",\"fct_orders\",\"dim_customer\",\"dim_product\",\"mart_daily_revenue\"]", "",
        *[f"ref table {t}" for t in TABLES], ""]))
    write(d / "expressions.tmdl", "\n".join([
        f'expression DataUrl = "{DATA_URL}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
        f"\tlineageTag: {uuid.uuid4()}", "", "\tannotation PBI_ResultType = Text", ""]))
    for t, cols in TABLES.items():
        write(d / "tables" / f"{t}.tmdl", table_tmdl(t, cols, MEASURES if t == "fct_orders" else ()))
    write(d / "relationships.tmdl", "\n".join([
        f"relationship {uuid.uuid4()}", "\tfromColumn: fct_orders.customer_id", "\ttoColumn: dim_customer.customer_id", "",
        f"relationship {uuid.uuid4()}", "\tfromColumn: fct_orders.product_id", "\ttoColumn: dim_product.product_id", ""]))


# ---------------------------------------------------------------- report
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"


def field(entity, prop, measure=False):
    kind = "Measure" if measure else "Column"
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(entity, prop, measure=False, active=False):
    p = {"field": field(entity, prop, measure), "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if active:
        p["active"] = True
    return p


def title_obj(text):
    return {"title": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}},
                                       "text": {"expr": {"Literal": {"Value": f"'{text}'"}}}}}]}


def visual(page_dir, x, y, w, h, vtype, query=None, objects=None, container=None, z=0):
    name = gid()
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if query:
        v["query"] = {"queryState": query}
    if objects:
        v["objects"] = objects
    if container:
        v["visualContainerObjects"] = container
    wjson(page_dir / "visuals" / name / "visual.json", {
        "$schema": VC, "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z}, "visual": v})


def card(page_dir, x, measure, z):
    visual(page_dir, x, 90, 290, 110, "cardVisual",
           {"Data": {"projections": [proj("fct_orders", measure, measure=True)]}}, z=z)


def bar(page_dir, x, y, w, h, entity, col, measure, title, z):
    visual(page_dir, x, y, w, h, "clusteredBarChart",
           {"Category": {"projections": [proj(entity, col, active=True)]},
            "Y": {"projections": [proj("fct_orders", measure, measure=True)]}},
           objects={"labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]},
           container=title_obj(title), z=z)


def build_report():
    wjson(RP / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid4())}})
    wjson(RP / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    d = RP / "definition"
    wjson(d / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"})
    theme = "Fluent2-CY26SU09"
    wjson(d / "report.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": theme, "reportVersionAtImport": {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}, "type": "SharedResources"}},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": theme, "path": f"BaseThemes/{theme}.json", "type": "BaseTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
    tdir = RP / "StaticResources" / "SharedResources" / "BaseThemes"
    tdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(THEME_SRC, tdir / f"{theme}.json")

    p1, p2 = gid(), gid()
    wjson(d / "pages" / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p1, p2], "activePageName": p1})

    # ---- page 1: sales overview
    pd = d / "pages" / p1
    wjson(pd / "page.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": p1, "displayName": "Sales Overview", "displayOption": "FitToPage", "height": 720, "width": 1280})
    visual(pd, 20, 15, 800, 60, "textbox", objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": "Shop Sales Dashboard", "textStyle": {"fontSize": "22pt", "fontWeight": "bold"}}]},
        {"textRuns": [{"value": "Net revenue after payments and refunds · data from the dbt marts (simulated data)", "textStyle": {"fontSize": "11pt"}}]}]}}]}, z=0)
    visual(pd, 1000, 15, 260, 60, "slicer",
           {"Values": {"projections": [proj("fct_orders", "country", active=True)]}},
           objects={"data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]}, z=1)
    for i, m in enumerate(["Net Revenue", "Orders", "Customers", "Cancel Rate"]):
        card(pd, 20 + i * 315, m, 10 + i)
    visual(pd, 20, 215, 1240, 230, "lineChart",
           {"Category": {"projections": [proj("fct_orders", "order_date", active=True)]},
            "Y": {"projections": [proj("fct_orders", "Net Revenue", measure=True)]}},
           container=title_obj("Net revenue per day"), z=20)
    bar(pd, 20, 460, 610, 245, "fct_orders", "country", "Net Revenue", "Net revenue by country", 21)
    bar(pd, 650, 460, 610, 245, "dim_product", "category", "Net Revenue", "Net revenue by product category", 22)

    # ---- page 2: products & customers
    pd = d / "pages" / p2
    wjson(pd / "page.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
        "name": p2, "displayName": "Products & Refunds", "displayOption": "FitToPage", "height": 720, "width": 1280})
    visual(pd, 20, 15, 800, 50, "textbox", objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": "Products, Refunds & Order Value", "textStyle": {"fontSize": "20pt", "fontWeight": "bold"}}]}]}}]}, z=0)
    for i, m in enumerate(["Gross Sales", "Refunds", "Refund Rate", "Avg Order Value"]):
        card(pd, 20 + i * 315, m, 10 + i)
    bar(pd, 20, 215, 610, 490, "dim_product", "product_name", "Net Revenue", "Net revenue by product", 20)
    bar(pd, 650, 215, 610, 490, "fct_orders", "status", "Orders", "Orders by status", 21)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    build_model()
    build_report()
    wjson(OUT / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    write(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"Power BI project written to {OUT.relative_to(ROOT)}/{NAME}.pbip")


if __name__ == "__main__":
    main()
