#!/usr/bin/env python3
"""Regression Test Suite - One-click runner

运行所有回归测试，输出聚合报告。

用法：
    python tests/regression/run_all.py
"""

import sys, os, json, datetime, importlib.util

GA_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, GA_ROOT)

REGRESSION_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(GA_ROOT, "temp")
RESULTS_FILE = os.path.join(GA_ROOT, "temp", "regression_results.json")


def _find(name_candidates, *dirs):
    """在多个目录中按候选名查找文件。"""
    for d in dirs:
        for n in name_candidates:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None


# 回归测试注册表
#   needs_api=True 表示该测试会发起真实 LLM API 调用（耗时/耗成本），
#   默认（safe 模式）跳过，仅 --full 时运行。
REGRESSION_TESTS = [
    # offline：SOP 对抗评估（不调用 API，评估内置响应）
    {
        "name": "sop_adversarial_eval",
        "path": _find(["sop_adversarial_eval.py"], TEMP_DIR, REGRESSION_DIR),
        "needs_api": False,
        "args": ["--dry-run"],
    },
    # offline：3 个 Skill 自测（纯本地）
    {
        "name": "skill_selftests",
        "path": None,  # 特殊：直接 import
        "needs_api": False,
        "special": "skills",
    },
    # offline：交叉验证管道自测（纯本地）
    {
        "name": "cross_validation",
        "path": None,
        "needs_api": False,
        "special": "cross_validation",
    },
    # online：多智能体全链路集成（6 场景，真实 API）
    {
        "name": "multiagent_integration",
        "path": _find(["multiagent_integration_test.py", "test_multiagent_integration.py"],
                      TEMP_DIR, REGRESSION_DIR),
        "needs_api": True,
    },
    # online：故障注入鲁棒性（真实 API）
    {
        "name": "fault_injection",
        "path": _find(["fault_injection_test.py", "test_fault_injection.py"],
                      TEMP_DIR, REGRESSION_DIR),
        "needs_api": True,
    },
]

# 目前从 temp/ 直接引用
# 后续逐步迁移到 tests/regression/


def load_report(filepath):
    """加载已有的测试结果文件用于基线对比。"""
    if os.path.exists(filepath):
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def run_test(spec) -> dict:
    """执行一个测试脚本并捕获输出。spec 为 REGRESSION_TESTS 中的条目。"""
    name = spec["name"]
    result = {
        "name": name,
        "path": spec.get("path"),
        "needs_api": spec.get("needs_api", False),
        "passed": False,
        "output": "",
        "error": None,
    }
    # 特殊：直接 import skill 自测
    if spec.get("special") == "skills":
        try:
            from memory.skills.web_deep_browse.skill import selftest as t1
            from memory.skills.feishu_group.skill import selftest as t2
            from memory.skills.fsapp_health.skill import health_check
            r1, r2 = t1(), t2()
            health_check()
            result["passed"] = True
            result["output"] = f"web_deep_browse={len(r1)}keys feishu_group={len(r2)}keys fsapp_health=ok"
            return result
        except Exception as e:
            result["passed"] = False
            result["error"] = f"skills: {e}"
            return result
    # 特殊：直接 import cross_validation 自测
    if spec.get("special") == "cross_validation":
        try:
            from memory.cross_validation import selftest
            r = selftest()
            ok = all(v == "ok" for v in r.values())
            result["passed"] = ok
            result["output"] = f"{sum(v=='ok' for v in r.values())}/{len(r)} checks passed"
            return result
        except Exception as e:
            result["passed"] = False
            result["error"] = f"cross_validation: {e}"
            return result
    path = spec.get("path")
    args = spec.get("args", [])
    if not path:
        result["error"] = "no path"
        return result
    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        # 注入 argv（如 --dry-run）
        old_argv = sys.argv
        sys.argv = [path] + list(args)
        out_buf = []
        import io, contextlib
        try:
            with contextlib.redirect_stdout(io.StringIO()) as sout:
                exec_globals = {"__name__": "__main__", "__file__": path}
                exec(code, exec_globals)
                out_buf.append(sout.getvalue())
        finally:
            sys.argv = old_argv
        result["passed"] = True
        result["output"] = (out_buf[0] or "")[-500:]
        return result
    except SystemExit as e:
        # sop_adversarial_eval 在不达标时 sys.exit(1)
        result["passed"] = (e.code == 0)
        result["error"] = f"exit code {e.code}" if e.code else None
        return result
    except Exception as e:
        result["passed"] = False
        result["error"] = str(e)
        return result


def run_all(full: bool = False) -> list:
    """运行所有回归测试。full=True 时包含需 API 的在线测试。"""
    results = []
    for spec in REGRESSION_TESTS:
        name = spec["name"]
        print(f"Running: {name}...", end=" ")
        if spec.get("needs_api") and not full:
            r = {"name": name, "passed": None, "error": "skipped (needs_api, use --full)",
                 "needs_api": True}
            print("SKIP (online)")
        elif not spec.get("path") and not spec.get("special"):
            r = {"name": name, "passed": None, "error": "File not found"}
            print("SKIP (File not found)")
        else:
            r = run_test(spec)
            status = "PASS" if r["passed"] else f"FAIL ({r['error']})"
            print(status)
        results.append(r)
    return results


def main():
    full = "--full" in sys.argv
    timestamp = datetime.datetime.now().isoformat()

    print("=" * 60)
    print(f"GA Regression Test Suite  {'[FULL]' if full else '[SAFE — offline only]'}")
    print(f"Timestamp: {timestamp}")
    print(f"Root: {GA_ROOT}")
    print("=" * 60)

    # 加载基线
    baseline = load_report(RESULTS_FILE)
    if baseline:
        print(f"Previous run: {baseline.get('timestamp', 'unknown')}")
        print(f"  {baseline.get('passed', 0)}/{baseline.get('total', 0)} passed")

    print()
    results = run_all(full=full)
    passed = sum(1 for r in results if r.get("passed") is True)
    failed = sum(1 for r in results if r.get("passed") is False)
    skipped = sum(1 for r in results if r.get("passed") is None)
    total = len(results)

    print()
    print("=" * 60)
    print(f"Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)

    report = {
        "timestamp": timestamp,
        "suite": "regression",
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "details": results,
        "baseline": baseline
    }

    with open(RESULTS_FILE, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report written: {RESULTS_FILE}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
