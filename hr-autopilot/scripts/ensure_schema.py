#!/usr/bin/env python3
"""补齐多维表格结构（考勤/请假用，无薪资字段）。幂等，可重复执行。

用法: python3 scripts/ensure_schema.py [--force-formula]
  --force-formula  覆盖已有公式（默认只填空公式）
"""
import sys

import fs

TEXT, NUMBER, DATE, USER, FORMULA = 1, 2, 5, 11, 20


def ensure_fields(app, table, wanted, existing):
    """wanted: [(name, type, prop)]；缺失则创建。"""
    names = {f["field_name"] for f in existing}
    for name, ftype, prop in wanted:
        if name in names:
            continue
        fs.create_field(app, table, name, ftype, prop)
        print(f"  + 新建字段 {name}")


def ensure_formula(app, table, existing, name, expr, force=False):
    fld = next((f for f in existing if f["field_name"] == name), None)
    if fld is None:
        fs.create_field(app, table, name, FORMULA, {"formula_expression": expr})
        print(f"  + 新建公式字段 {name} = {expr}")
        return
    if fld["type"] != FORMULA:
        print(f"  ! {name} 已存在但不是公式字段，跳过")
        return
    cur = (fld.get("property") or {}).get("formula_expression") or ""
    if cur and not force:
        return
    fs.update_field(app, table, fld["field_id"], name, FORMULA, {"formula_expression": expr})
    print(f"  ✓ 写入公式 {name} = {expr}")


def main():
    force = "--force-formula" in sys.argv
    cfg = fs.load_config()
    app = fs.app_token_from_url(cfg["base_url"])
    t = {k: fs.table_id_by_name(app, v) for k, v in cfg["tables"].items()}

    print("[员工管理]")
    emp_fields = fs.list_fields(app, t["employee"])
    ensure_fields(app, t["employee"], [
        ("飞书账号", USER, {"multiple": False}),
    ], emp_fields)

    print("[考勤管理]")
    att_fields = fs.list_fields(app, t["attendance"])
    ensure_fields(app, t["attendance"], [
        ("工号", TEXT, None),
        ("年假已用", NUMBER, {"formatter": "0.0"}),
    ], att_fields)
    att_fields = fs.list_fields(app, t["attendance"])
    ensure_formula(app, t["attendance"], att_fields, "年假剩余", "[年假]-[年假已用]", force=True)

    print("[加班管理]")
    ot_fields = fs.list_fields(app, t["overtime"])
    ensure_fields(app, t["overtime"], [("工号", TEXT, None)], ot_fields)

    print("表结构检查完成 ✅")


if __name__ == "__main__":
    main()
