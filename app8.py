from flask import Flask, render_template, request, jsonify, send_from_directory, abort
import pandas as pd
import folium
import os
import json

app = Flask(__name__)

# Load your dataset
df = pd.read_csv(r"final dataset.csv")

# Clean column names to remove special characters and spaces
df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("Â", "")


# Define desired output format
desired_format = "%d-%m-%Y %H:%M"

# Attempt parsing with first format (mm/dd/yy)
df["Parsed_Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y %H:%M", errors="coerce")

# Parse remaining unparsed dates (NaT) with second format (dd-mm-yyyy)
df["Parsed_Date"] = df["Parsed_Date"].fillna(
    pd.to_datetime(df["Date"], format="%d-%m-%Y %H:%M", errors="coerce")
)

# Format all dates to desired format
df["Date"] = df["Parsed_Date"].dt.strftime(desired_format)

# Preprocess data
df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y %H:%M", errors="coerce")
df.dropna(subset=["Date"], inplace=True)

# Prepare unique values for dropdowns
unique_latitudes = df["Y"].unique().tolist()  # Use Y for latitude
unique_longitudes = df["X"].unique().tolist()  # Use X for longitude
unique_dates = pd.to_datetime(df["Date"]).dt.date.unique().tolist()
unique_zip = df["Zip_Code"].unique().tolist()  # Use X for longitude

# Combine latitude and longitude into a single option
unique_lat_lon_pairs = [
    f"{lon} & {lat}" for lat, lon in zip(unique_latitudes, unique_longitudes)
]

# Get min and max date for validation
min_date = df["Date"].min().date()
max_date = df["Date"].max().date()

# Load JSON file with soil colors and crop icons
json_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(json_path, "r") as f:
    config = json.load(f)

soil_colors_html = config["soil_types"]
crop_colors_html = config["crops"]


@app.route("/")
def index():
    return render_template(
        "dashboard.html",
        unique_lat_lon_pairs=unique_lat_lon_pairs,
        unique_dates=unique_dates,
        min_date=min_date,
        max_date=max_date,
        zip_codes=unique_zip,
    )


@app.route("/get_data", methods=["POST"])
def get_data():
    request_data = request.get_json()
    filtered_data = df

    if request_data["zip_code"]:
        zip_code = str(request_data["zip_code"])
        filtered_data["Zip_Code"] = filtered_data["Zip_Code"].astype(str)
        filtered_data = filtered_data[filtered_data["Zip_Code"] == zip_code]

    if request_data["start_date"]:
        start_date = pd.to_datetime(request_data["start_date"])
        filtered_data = filtered_data[(filtered_data["Date"] >= start_date)]

    if request_data["end_date"]:
        end_date = pd.to_datetime(request_data["end_date"])
        filtered_data = filtered_data[(filtered_data["Date"] <= end_date)]

    if filtered_data.empty:
        return jsonify({"error": "No data found for the selected parameters."}), 404

    # Sort data by Date in ascending order
    filtered_data = filtered_data.sort_values(by="Date", ascending=True)

    # Create Map 1 (pins for data points)
    map_1 = folium.Map(
        location=[filtered_data["Y"].mean(), filtered_data["X"].mean()], zoom_start=7
    )

    # Adding markers for Map 1
    for _, row in filtered_data.iterrows():
        folium.Marker(
            [row["Y"], row["X"]],
            popup=folium.Popup(
                f"<strong>Date:</strong> {row['Date'].date()}<br>"
                f"<strong>Temperature:</strong> {row['Temperature_(°C)']} °C<br>"
                f"<strong>Humidity:</strong> {row['Humidity_(%)']} %<br>"
                f"<strong>Precipitation:</strong> {row['Precipitation_(mm)']} mm",
                max_width=300,
            ),
        ).add_to(map_1)

    map_1_path = "static/map_1.html"
    map_1.save(map_1_path)

    # Create Map 2 with colored regions based on soil type
    map_2 = folium.Map(
        location=[filtered_data["Y"].mean(), filtered_data["X"].mean()], zoom_start=7
    )

    # Define soil color mapping
    soil_colors = {
        "Alluvial Soils": "lightgreen",
        "Clay": "brown",
        "Clay Loam": "darkbrown",
        "Gravelly Loam": "tan",
        "Loam": "yellow",
        "Sandy Loam": "gold",
        "Silt Loam": "gray",
    }

    # Adding colored regions for Map 2
    for _, row in filtered_data.iterrows():
        # Add a CircleMarker to represent soil type
        folium.CircleMarker(
            location=[row["Y"], row["X"]],
            radius=20,  # Increased diameter for better visibility
            color=soil_colors.get(
                row["Soil_Type"], "gray"
            ),  # Default to gray if soil type not found
            fill=True,
            fill_color=soil_colors.get(row["Soil_Type"], "gray"),
            fill_opacity=0.6,
        ).add_to(map_2)

        # Representing crops visually using icons
        crop_type = row["Crops_Grown"]

        # Dictionary for crop icons and colors
        crop_icons = {
            "Almonds": ("leaf", "green"),
            "Artichokes": ("leaf", "purple"),
            "Barley": ("leaf", "brown"),
            "Beans": ("leaf", "yellow"),
            "Beets": ("leaf", "red"),
            "Broccoli": ("leaf", "darkgreen"),
            "Carrots": ("carrot", "orange"),
            "Cauliflower": ("leaf", "white"),
            "Chard": ("leaf", "lightgreen"),
            "Cotton": ("leaf", "pink"),
            "Garlic": ("star", "white"),
            "Grapes": ("leaf", "purple"),
            "Lettuce": ("leaf", "lightgreen"),
            "Melons": ("leaf", "yellow"),
            "Okra": ("leaf", "green"),
            "Onions": ("leaf", "purple"),
            "Peppers": ("leaf", "red"),
            "Spinach": ("leaf", "darkgreen"),
            "Tomatoes": ("leaf", "red"),
            "Walnuts": ("leaf", "brown"),
            "Wheat": ("leaf", "yellow"),
        }

        if crop_type in crop_icons:
            # Generate the soil and crop type names in lowercase and with underscores to match the image filenames
            soil_image_name = row["Soil_Type"].lower().replace(" ", "_")
            crop_image_name = crop_type.lower().replace(" ", "_")

            # Define the path to the images
            soil_image_path = f"images/{soil_image_name}.png"
            crop_image_path = f"images/{crop_image_name}.png"
            icon, color = crop_icons[crop_type]

            folium.Marker(
                location=[row["Y"], row["X"]],
                icon=folium.Icon(icon=icon, color=color),
                popup=folium.Popup(
                    f"""
                    <table style="width: 100%; border: none;">
                        <tr>
                            <td><strong>Soil Type:</strong> {row['Soil_Type']}</td>
                            <td style="padding-left: 20px;"><strong>Crop Type:</strong>{crop_type}</td>
                        </tr>
                        <tr>
                            <td><img src="{soil_image_path}" alt="{row['Soil_Type']} image" width="100"></td>
                            <td style="padding-left: 20px;"><img src="{crop_image_path}" alt="{crop_type} image" width="100"></td>
                        </tr>
                    </table>
                    """,
                    max_width=500,
                ),
            ).add_to(map_2)

    map_2_path = "static/map_2.html"
    map_2.save(map_2_path)

    # Prepare response data for table
    response_data = []
    for _, row in filtered_data.iterrows():
        response_data.append(
            {
                "date": row["Date"].date(),
                "Soil_Moisture": row["Soil_Moisture"],
                "Nitrogen": row["Nitrogen"],
                "Soil_ph_value": row["Soil_ph_value"],
                "soil_type": row["Soil_Type"],
                "crop_type": row["Crops_Grown"],
                "Soil_Carbon": row["Soil_Carbon"],
                "Soil_Temperature": row["soil_temperature_18cm_(°C)"],
                "zip_code": row["Zip_Code"],
            }
        )

    # Get unique soil types and crop types
    unique_soil_types = filtered_data["Soil_Type"].unique().tolist()
    unique_crop_types = filtered_data["Crops_Grown"].unique().tolist()
    print(unique_crop_types, unique_soil_types)

    # Filter only colors for soil and crop types present in unique lists
    filtered_soil_colors = [
        {"name": item["name"], "color": item["color"]}
        for item in soil_colors_html
        if item["name"] in unique_soil_types
    ]
    filtered_crop_colors = [
        {"name": item["name"], "color": item["color"]}
        for item in crop_colors_html
        if item["name"] in unique_crop_types
    ]

    return jsonify(
        {
            "map_1": map_1_path,
            "map_2": map_2_path,
            "data": response_data,
            "soil_colors": filtered_soil_colors,
            "crop_icons": filtered_crop_colors,
        }
    )


if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")
    app.run(debug=True)
