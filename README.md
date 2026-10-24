# Entity and Event Indexes for State, Continuity and Counting Questions over Verbatim Million-Token Records

Data, code and stored model outputs of the paper of this title (under review).

- What is in this release, how to replay the 39 tables and analyses and three figures listed in the replay report without model access, and how to re-run one
  condition with model access: [release/README.md](release/README.md)
- Third-party benchmarks (not redistributed here) and how to download and prepare them:
  [release/THIRD_PARTY_DATA.md](release/THIRD_PARTY_DATA.md)
- Every change made when this copy was made from the working tree: [RELEASE_NOTES.md](RELEASE_NOTES.md)
- Manuscript and supplementary material: [paper/manuscript_final_en.md](paper/manuscript_final_en.md),
  [paper/supplement_final_en.md](paper/supplement_final_en.md)
- sha256 of every file as published: [release/RELEASE_FILES_SHA256.txt](release/RELEASE_FILES_SHA256.txt)

## Replaying the tables

No model client or model access is needed.

```
pip install -r release/requirements_replay.txt
# prepare the third-party data as release/THIRD_PARTY_DATA.md describes, then:
python release/restore_third_party_fields.py
python release/reproduce_tables.py
```

`release/reproduce_tables.py` recomputes the 39 reported tables and analyses and the 3 figures from the stored outputs
and checks each against the table files of `paper/`; it exits 1 if any of its 42 checks fails.

## Licence

Code under the MIT License; data and stored outputs under CC BY 4.0, with the exceptions listed in
[LICENSE](LICENSE).
