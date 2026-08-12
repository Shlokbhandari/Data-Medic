import pandas as pd

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {len(df)}')

    df = df.sort_values(by='order_date').drop_duplicates(subset=['transaction_id'], keep='first')
    df = df.dropna(subset=['price'])
    
    print(f'Rows after cleaning: {len(df)}')

    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()