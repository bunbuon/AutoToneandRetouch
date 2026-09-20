"""Smoke test: chay that cac luong chinh cua GUI, bat loi runtime nhu NameError."""
import sys, time
sys.path.insert(0, r"f:\Claude AI\AutoToneImages")
import tkinter as tk, autotone_gui as g, autotone as at

FAIL = []
def check(name, fn):
    try:
        fn(); print(f"  OK   {name}")
    except Exception as e:
        FAIL.append((name, e)); print(f"  LOI  {name}: {type(e).__name__}: {e}")

def main():
    r = tk.Tk(); r.withdraw(); app = g.App(r); r.update()
    print("Smoke test giao dien:")
    check("read_cfg",        lambda: app.read_cfg())
    check("scan_folder",     lambda: (app.v_folder.set(r"G:\Test"), app.scan_folder()))
    check("_set_busy",       lambda: (app._set_busy(True), app._set_busy(False)))
    check("refresh_job_state", lambda: app.refresh_job_state())
    check("_watch_job",      lambda: app._watch_job(at.LR_JOB_DIR/"khong_co.tsv"))
    check("safe_jobs",       lambda: at.safe_jobs(8, app.read_cfg()))

    # luong phan tich that
    app.pairs = app.pairs[:8]
    check("start_analyze", lambda: app.start_analyze())
    t0 = time.time()
    while app.busy and time.time()-t0 < 300:
        r.update(); time.sleep(0.05)
    r.update()
    if app.busy:
        FAIL.append(("phan tich", "treo qua 300s")); print("  LOI  phan tich treo")
    elif not app.items:
        FAIL.append(("phan tich", "khong ra item")); print("  LOI  phan tich khong ra ket qua")
    else:
        print(f"  OK   phan tich ({len(app.items)} anh)")
        check("refresh_plan", lambda: app.refresh_plan())
        check("_fill_table",  lambda: app._fill_table())
        check("sent_values",  lambda: at.sent_values(app.items[0]["path"]))
    r.destroy()
    print()
    print("TAT CA OK" if not FAIL else f"{len(FAIL)} LOI: " +
          ", ".join(n for n,_ in FAIL))
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    main()
