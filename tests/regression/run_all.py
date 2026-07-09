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
RESULTS_FILE = os.path.join(GA_ROOT, "temp", "regression_results.json")


# 回归测试注册表
REGRESSION_TESTS = [
    # (模块名, 路径)
    ("test_fault_injection", os.path.join(REGRESSION_DIR, "test_fault_injection.py")),
    ("test_multiagent_integration", os.path.join(REGRESSION_DIR, "test_multiagent_integration.py")),
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


def run_test(name, path) -> dict:
    """执行一个测试脚本并捕获输出。"""
    result = {
        "name": name,
        "path": path,
        "passed": False,
        "output": "",
        "error": None,
    }
    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        exec_globals = {"__name__": "__main__", "__file__": path}
        exec(code, exec_globals)
        result["passed"] = True
        result["output"] = os.path.join(GA_ROOT, "temp", f"{name}_output.txt")
        return result
    except Exception as e:
        result["passed"] = False
        result["error"] = str(e)
        return result


def run_all() -> list:
    """运行所有回归测试。"""
    results = []
    for name, path in REGRESSION_TESTS:
        print(f"Running: {name}...", end=" ")
        if os.path.exists(path):
            r = run_test(name, path)
            status = "PASS" if r["passed"] else f"FAIL ({r['error']})"
            print(status)
        else:
            r = {"name": name, "passed": None, "error": f"File not found: {path}"}
            print(f"SKIP ({r['error']})")
        results.append(r)
    return results


def main():
    timestamp = datetime.datetime.now().isoformat()

    print("=" * 60)
    print(f"GA Regression Test Suite")
    print(f"Timestamp: {timestamp}")
    print(f"Root: {GA_ROOT}")
    print("=" * 60)

    # 加载基线
    baseline = load_report(RESULTS_FILE)
    if baseline:
        print(f"Previous run: {baseline.get('timestamp', 'unknown')}")
        print(f"  {baseline.get('passed', 0)}/{baseline.get('total', 0)} passed")

    print()
    results = run_all()
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
