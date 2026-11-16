# Copilot Studio version of the Ferrero assistant (optional)

An optional track, built by an ordinary Copilot Studio user: no admin rights, no Entra ID, no SharePoint site, no Fabric. Nothing in `src/ferrero` reads or calls anything here, so the Python/Claude build works whether or not this is finished.

| File | Where it goes |
|---|---|
| `knowledge/case_documents/` | The 12 pack documents. Upload them all at once as one file group named "Case documents" |
| `knowledge/Case_Tracker_Snapshot_2026-11-05.docx` | Upload as its own file, "Case tracker snapshot". It answers the count, total and status questions |
| `agent_instructions.txt` | Agent > Overview > Instructions |
| `descriptions.txt` | The agent's description and the two knowledge descriptions |
| `eval_documents.csv`, `eval_analytics.csv` | Evaluation > New evaluation > Single responses > Import |
| `make_snapshot.py`, `make_eval_csvs.py` | Rebuild the snapshot and the evaluation files if the pack's CSVs change |
| `optional_admin_path/` | Only for the full version with admin help (SharePoint upload, Fabric data agent). Not needed for the demo |

Notes
- The snapshot is the case tracker frozen at the demo date (5 Nov 2026), with the figures pre-computed: KSA open cases 9, hearings in the next 30 days 8, damages awarded in 2025 AED 9,323,640, and so on. It isn't live; rebuild it with `python make_snapshot.py` if the data changes.
- Four expected answers in the evaluation files are rewritten (see `make_eval_csvs.py`): GS-017, GS-025, GS-026 and GS-028 (a tie at 7 cases).
- Per-user security (UAE counsel sees only UAE cases) needs test accounts and SharePoint permissions, which need an admin. In this version, everyone who uses the agent sees every uploaded file.
