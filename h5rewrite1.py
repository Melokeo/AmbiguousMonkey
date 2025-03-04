import pandas as pd
import numpy as np
Ref = [
    {
        'Fixed1': (100, 200, 1),
        'Fixed2': (300, 400, 1),
        'Fixed3': (500, 600, 1)
    },
    {
        'Fixed1': (100, 200, 1),
        'Fixed2': (300, 400, 1),
        'Fixed3': (500, 600, 1)
    },
    {
        'Fixed1': (100, 200, 1),
        'Fixed2': (300, 400, 1),
        'Fixed3': (500, 600, 1)
    },
    {
        'Fixed1': (100, 200, 1),
        'Fixed2': (300, 400, 1),
        'Fixed3': (500, 600, 1)
    }]


def add_fixed_points(input_file, output_file, cam, Ref):
    # Load the .h5 file
    df = pd.read_hdf(input_file)
    
    # Define new fixed points and their fixed values
    new_points = Ref[cam-1]
    
    num_rows = df.shape[0]  # Keep the same number of rows

    # Flatten the fixed values and repeat them for all rows
    fixed_values = np.tile(np.array(list(new_points.values())).flatten(), (num_rows, 1))

    # Create a DataFrame for new points
    new_data = pd.DataFrame(
        fixed_values,
        columns=pd.MultiIndex.from_product(
            [[df.columns.levels[0][0]], new_points.keys(), ['x', 'y', 'likelihood']],
            names=df.columns.names
        )
    )
    
    # Append new columns to the existing DataFrame
    df = pd.concat([df, new_data], axis=1)
    
    # Save the modified DataFrame
    df.to_hdf(output_file, key="df", mode="w")
    print(f"Modified file saved as: {output_file}")

if __name__ == "__main__":
    input_file = "250123-pici-ts-cam1.h5"  # Update with your actual file path
    output_file = "250123-pici-ts-cam1-modified.h5"
    cam = int(input_file.split('.')[0][-1])
    add_fixed_points(input_file, output_file, cam, 1)
