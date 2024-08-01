import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import mean_squared_error
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# Load the data from Excel file
file_path = r"C:\Users\Yucehan Kutlu\Documents\Data Science\DataGen\DATA\Wind2013_2023.xlsx"
df = pd.read_excel(file_path, sheet_name='Sheet1')

# Assuming the time series data is in a column named 'value'
# Adjust column name as per your data
df['date'] = pd.to_datetime(df['date'])  # Adjust 'date' to your actual datetime column
df.set_index('date', inplace=True)
time_series_data = df['electricity']

# Split the data into training and testing sets (80% training, 20% testing)
train_size = int(len(time_series_data) * 0.8)
train, test = time_series_data[:train_size], time_series_data[train_size:]

# Define SARIMA model
# Parameters (p, d, q) for ARIMA and (P, D, Q, m) for seasonal components
p, d, q = 1, 1, 1
P, D, Q, m = 1, 1, 1, 24  # Adjust m based on your seasonality (24 for daily seasonality in hourly data)

# Fit SARIMA model
sarima_model = sm.tsa.SARIMAX(train, order=(p, d, q), seasonal_order=(P, D, Q, m))
sarima_results = sarima_model.fit()

# Print the summary of the model
print(sarima_results.summary())

# Make predictions on the test set
predictions = sarima_results.get_forecast(steps=len(test))
predicted_mean = predictions.predicted_mean
pred_conf_int = predictions.conf_int()

# Evaluate the model
mse = mean_squared_error(test, predicted_mean)
print(f'Test MSE: {mse:.3f}')

# Plot the training data, test data, and predictions
plt.figure(figsize=(14, 7))
plt.plot(train, label='Training Data')
plt.plot(test.index, test, label='Test Data')
plt.plot(test.index, predicted_mean, label='Predictions')
plt.fill_between(test.index, pred_conf_int.iloc[:, 0], pred_conf_int.iloc[:, 1], color='pink', alpha=0.3)
plt.legend()
plt.title('Training, Test Data and Predictions')
plt.show()

# Generate synthetic data for one year (365*24 hours)
forecast_steps = 365 * 24
forecast = sarima_results.get_forecast(steps=forecast_steps)
synthetic_data = forecast.predicted_mean

# Check if synthetic_data is empty or not
print("Synthetic Data Sample:")
print(synthetic_data.head())

# Create a new DataFrame for the synthetic data
if not synthetic_data.empty:
    last_date = df.index[-1]
    synthetic_dates = pd.date_range(start=last_date, periods=forecast_steps + 1, freq='H')[1:]
    synthetic_df = pd.DataFrame(synthetic_data, index=synthetic_dates, columns=['synthetic_value'])

    # Plot the original data and synthetic data
    plt.figure(figsize=(14, 7))
    plt.plot(time_series_data.tail(365*24), label='Original Data (Last Year)')
    plt.plot(synthetic_df['synthetic_value'], label='Synthetic Data (One Year)')
    plt.legend()
    plt.title('Original and Synthetic Hourly Data')
    plt.show()

    # Save the synthetic data to a new sheet in the Excel file
    with pd.ExcelWriter("Synthetic Data.xlsx") as writer:
        synthetic_df.to_excel(writer, sheet_name='Synthetic Data')
else:
    print("Synthetic data is empty. Check the model fitting and forecasting process.")

