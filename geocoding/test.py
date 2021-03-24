import pandas as pd

xlsx_name = "ReportedTravel.xlsx"
temp = pd.ExcelFile(xlsx_name)
sheet_names = temp.sheet_names

total = 0
nones = 0

for sheet_name in sheet_names:
    df = pd.read_csv(f"Sheets/{sheet_name}.csv")
    total += len(df)
    nones += len(df) - df["Latitude"].count()
    if len(set(df["geocoded"].tolist())) > 1:
        print(f"Sheet - {sheet_name} was not geocoded completey.")

print(total, nones)
