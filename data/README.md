# Input data

Place the organizers' `chars_final_with_names.parquet` here, or set `FIAM_DATA_DIR`
to its containing directory. This large original dataset is not committed.

Included: `factor_char_list.csv`, `external/SP500_fred.csv`, `external/TB3MS.csv`.
Saved prediction columns are committed separately in `prediction/saved_forecasts`.
No daily-return dataset is bundled. That input is still needed for the remaining
final-challenge execution and reporting work.
