import pandas as pd
import requests

params = {"format": "json"}

df = pd.DataFrame(
    requests.get("https://waterwatch.usgs.gov/webservices/realtime",
                 params=params).json()["sites"])

county_dict = {
    "site_no": [],
    "county_fips": [],
    "state_nm": [],
    "county_nm": [],
    "state_code": []
}
for row in df.itertuples():

    fcc_request = requests.get("https://geo.fcc.gov/api/census/block/find",
                               params={
                                   "latitude": row.dec_lat_va,
                                   "longitude": row.dec_long_va,
                                   "format": "json"
                               }).json()

    county_dict["site_no"].append(row.site_no)
    county_dict["county_fips"].append(fcc_request["County"]["FIPS"])
    county_dict["county_nm"].append(fcc_request["County"]["name"])
    county_dict["state_code"].append(fcc_request["State"]["code"])
    county_dict["state_nm"].append(fcc_request["State"]["name"])

county_df = pd.DataFrame(county_dict)

county_df.to_csv("county_lookup.csv", index=False)
