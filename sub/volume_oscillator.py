class VolumeOscillator:
    def __init__(self, short_period=5, long_period=14):
        self.short_period = short_period
        self.long_period = long_period
        self.volumes = []

    def determine_next_trade(self, candles, short_period=5, long_period=14):
        volumes = [candle[5] for candle in candles]  # Extract volume field
        close_prices = [candle[2] for candle in candles]  # Extraer precios de cierre
        open_prices = [candle[1] for candle in candles]  # Extraer precios de apertura
        
        oscillator_value = self.calculate_volume_oscillator(volumes, short_period, long_period)
        oscillator_closevalue = self.calculate_volume_oscillator(close_prices, short_period, long_period)
        
        trade_direction = self.analyze_trade_direction(oscillator_value,oscillator_closevalue)
        return trade_direction, oscillator_value
        
    def analyze_trade_direction(self, oscillator_value,vdir):
    
      if vdir > 0:  
        if oscillator_value > 0:
            return "call"  # Buy signal
        elif oscillator_value < 0:
            return "put"  # Sell signal
        else:
            return "hold"  # Neutral
      else:  
        if oscillator_value > 0:
            return "put"  # Buy signal
        elif oscillator_value < 0:
            return "call"  # Sell signal
        else:
            return "hold"  # Neutral      
        
    def calculate_volume_oscillator(self, volumes, short_period, long_period):
        if len(volumes) < long_period:
            raise ValueError("Not enough data to calculate the long-period SMA.")

        short_sma = self.calculate_sma(volumes, short_period)
        long_sma = self.calculate_sma(volumes, long_period)

        if long_sma == 0:  # Prevent division by zero
            return 0

        oscillator = ((short_sma - long_sma) / long_sma) * 100
        return round(oscillator, 2)
    
    def calculate_sma(self, data, period):
        if len(data) < period:
            return None  # Not enough data for the period
        return sum(data[-period:]) / period