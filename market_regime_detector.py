#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم تشخیص رژیم بازار (Market Regime Detection)
شناسایی شرایط بازار و انتخاب استراتژی‌های مناسب

رژیم‌های بازار:
1. 🔥 روند صعودی قوی (Strong Bull Trend)
2. ❄️ روند نزولی قوی (Strong Bear Trend)
3. 🔄 بازار رنج/خنثی (Sideways/Range)
4. ⚡ نوسان شدید/بحران (High Volatility/Crisis)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

class MarketRegimeDetector:
    """تشخیص رژیم‌های بازار با روش‌های مختلف"""

    def __init__(self, lookback_periods: Dict[str, int] = None):
        """
        Parameters:
        -----------
        lookback_periods: دوره‌های مختلف برای محاسبات
            - 'short': 5-10 روز (کوتاه‌مدت)
            - 'medium': 20 روز (میان‌مدت)
            - 'long': 50-100 روز (بلند‌مدت)
        """
        self.lookback = lookback_periods or {
            'short': 5,
            'medium': 20,
            'long': 50
        }

        self.regimes = {
            0: "🔥 روند صعودی قوی",
            1: "❄️ روند نزولی قوی",
            2: "🔄 بازار رنج",
            3: "⚡ نوسان شدید"
        }

    # ========== مهندسی ویژگی‌ها (Feature Engineering) ==========

    def calculate_returns(self, prices: pd.Series, periods: List[int] = None) -> pd.DataFrame:
        """محاسبهٔ بازدهی برای دوره‌های مختلف"""
        if periods is None:
            periods = [1, 5, 20]

        returns = pd.DataFrame(index=prices.index)
        for period in periods:
            returns[f'return_{period}d'] = prices.pct_change(period) * 100

        return returns

    def calculate_volatility(self, prices: pd.Series, window: int = 20) -> pd.Series:
        """محاسبهٔ نوسان‌پذیری محقق‌شده (Realized Volatility)"""
        returns = prices.pct_change() * 100
        volatility = returns.rolling(window=window).std()
        return volatility

    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series,
                      period: int = 14) -> pd.Series:
        """محاسبهٔ Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series,
                      period: int = 14) -> pd.Series:
        """محاسبهٔ Average Directional Index (ADX)"""
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = self.calculate_atr(high, low, close, period)

        plus_di = 100 * plus_dm.rolling(window=period).mean() / tr
        minus_di = 100 * minus_dm.rolling(window=period).mean() / tr

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx.fillna(0)

    def calculate_trend_strength(self, prices: pd.Series, window: int = 20) -> pd.Series:
        """محاسبهٔ قدرت روند (شیب خط رگرسیون)"""
        trend_strength = pd.Series(index=prices.index, dtype=float)

        for i in range(window, len(prices)):
            x = np.arange(window)
            y = prices.iloc[i-window:i].values
            z = np.polyfit(x, y, 1)
            slope = z[0]
            # نرمال‌سازی شیب
            normalized_slope = (slope / np.mean(y)) * 100 if np.mean(y) != 0 else 0
            trend_strength.iloc[i] = normalized_slope

        return trend_strength.fillna(0)

    def calculate_skewness(self, returns: pd.Series, window: int = 20) -> pd.Series:
        """محاسبهٔ عدم تقارن (Skewness) - آیا صعود بیشتر است یا نزول؟"""
        from scipy.stats import skew
        skewness = returns.rolling(window=window).apply(skew, raw=True)
        return skewness.fillna(0)

    def calculate_relative_volume(self, volume: pd.Series, window: int = 20) -> pd.Series:
        """محاسبهٔ حجم نسبی"""
        avg_volume = volume.rolling(window=window).mean()
        relative_volume = volume / avg_volume
        return relative_volume.fillna(1)

    def extract_features(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        استخراج تمام ویژگی‌ها

        Parameters:
        -----------
        ohlcv: DataFrame با ستون‌های ['Open', 'High', 'Low', 'Close', 'Volume']

        Returns:
        --------
        DataFrame با تمام ویژگی‌های محاسبه‌شده
        """
        features = pd.DataFrame(index=ohlcv.index)

        # بازدهی
        returns_df = self.calculate_returns(ohlcv['Close'])
        features = pd.concat([features, returns_df], axis=1)

        # نوسان‌پذیری
        features['volatility_20d'] = self.calculate_volatility(ohlcv['Close'], window=20)
        features['volatility_50d'] = self.calculate_volatility(ohlcv['Close'], window=50)

        # ATR و ADX
        features['atr_14'] = self.calculate_atr(ohlcv['High'], ohlcv['Low'],
                                                 ohlcv['Close'], period=14)
        features['adx_14'] = self.calculate_adx(ohlcv['High'], ohlcv['Low'],
                                                 ohlcv['Close'], period=14)

        # قدرت روند
        features['trend_strength_20'] = self.calculate_trend_strength(
            ohlcv['Close'], window=20
        )

        # عدم تقارن
        features['skewness_20'] = self.calculate_skewness(
            ohlcv['Close'].pct_change() * 100, window=20
        )

        # حجم نسبی
        features['relative_volume'] = self.calculate_relative_volume(
            ohlcv['Volume'], window=20
        )

        return features

    # ========== روش Rule-Based (Rule-Based / Heuristic) ==========

    def detect_regime_rule_based(self, features: pd.DataFrame) -> Tuple[List[int], pd.DataFrame]:
        """
        تشخیص رژیم بر اساس قواعین ساده

        منطق:
        - اگر ADX > 25 و Trend > 0 → روند صعودی
        - اگر ADX > 25 و Trend < 0 → روند نزولی
        - اگر ADX < 20 و Volatility متوسط → رنج
        - اگر ATR > 2x میانگین → نوسان شدید
        """
        regimes = []
        scores = pd.DataFrame(index=features.index)

        adx_threshold_strong = 25
        adx_threshold_weak = 20
        atr_multiplier = 2.0

        atr_mean = features['atr_14'].rolling(window=30).mean()

        for i in range(len(features)):
            if pd.isna(features.iloc[i].values).any():
                regimes.append(2)  # رنج (ایمن‌ترین)
                continue

            adx = features.iloc[i]['adx_14']
            trend = features.iloc[i]['trend_strength_20']
            volatility = features.iloc[i]['volatility_20d']
            atr = features.iloc[i]['atr_14']
            atr_avg = atr_mean.iloc[i]

            # نوسان شدید (بدترین شرایط)
            if atr > atr_multiplier * atr_avg:
                regime = 3
            # روند قوی
            elif adx > adx_threshold_strong:
                if trend > 0:
                    regime = 0  # صعودی
                else:
                    regime = 1  # نزولی
            # بازار رنج
            elif adx < adx_threshold_weak:
                regime = 2
            else:
                regime = 2  # پیش‌فرض: رنج

            regimes.append(regime)

        return regimes, pd.DataFrame({'regime_rule_based': regimes}, index=features.index)

    # ========== روش Hidden Markov Model (HMM) ==========

    def detect_regime_hmm(self, features: pd.DataFrame, n_states: int = 4) -> Tuple[List[int], pd.DataFrame]:
        """
        تشخیص رژیم با Hidden Markov Model
        نیاز: pip install hmmlearn

        Returns:
        --------
        - regimes: لیست رژیم‌های شناسایی‌شده
        - probabilities: احتمالات برای هر رژیم
        """
        try:
            from hmmlearn import hmm
        except ImportError:
            print("⚠️ hmmlearn نصب نشده. روش Rule-Based استفاده می‌شود.")
            return self.detect_regime_rule_based(features)

        # انتخاب ویژگی‌های کلیدی
        feature_cols = ['return_5d', 'volatility_20d', 'adx_14']
        X = features[feature_cols].fillna(0).values

        # آموزش مدل
        model = hmm.GaussianHMM(n_components=n_states, covariance_type="full", n_iter=1000)
        model.fit(X)

        # پیش‌بینی رژیم و احتمالات
        hidden_states = model.predict(X)
        probabilities = model.predict_proba(X)

        # ذخیره احتمالات
        prob_df = pd.DataFrame(
            probabilities,
            index=features.index,
            columns=[f'prob_state_{i}' for i in range(n_states)]
        )

        return hidden_states.tolist(), prob_df

    # ========== روش Unsupervised ML (K-Means / GMM) ==========

    def detect_regime_clustering(self, features: pd.DataFrame, n_clusters: int = 4) -> Tuple[List[int], pd.DataFrame]:
        """
        تشخیص رژیم با Clustering (K-Means)

        Parameters:
        -----------
        n_clusters: تعداد خوشه‌ها (معمولاً 4)

        Returns:
        --------
        - regimes: شناسایی‌شدهٔ رژیم برای هر روز
        - distances: فاصله از مراکز خوشه‌ها
        """
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans

        # انتخاب ویژگی‌های کلیدی و نرمال‌سازی
        feature_cols = ['return_5d', 'volatility_20d', 'adx_14', 'trend_strength_20']
        X = features[feature_cols].fillna(0).values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # آموزش K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X_scaled)

        # نرمال‌سازی cluster labels به regimes
        # (باید برچسب‌های خوشه‌ها را بر اساس ویژگی‌هایشان برچسب‌گذاری کنیم)
        regimes = self._label_clusters(clusters, features, kmeans)

        cluster_df = pd.DataFrame({
            'cluster': clusters,
            'regime': regimes
        }, index=features.index)

        return regimes, cluster_df

    def _label_clusters(self, clusters: np.ndarray, features: pd.DataFrame, kmeans) -> List[int]:
        """برچسب‌گذاری خوشه‌ها به رژیم‌های معنی‌دار"""
        cluster_characteristics = {}

        for cluster_id in range(kmeans.n_clusters):
            mask = clusters == cluster_id
            avg_volatility = features[mask]['volatility_20d'].mean()
            avg_adx = features[mask]['adx_14'].mean()
            avg_trend = features[mask]['trend_strength_20'].mean()

            cluster_characteristics[cluster_id] = {
                'volatility': avg_volatility,
                'adx': avg_adx,
                'trend': avg_trend
            }

        # تعیین رژیم برای هر خوشه
        cluster_to_regime = {}

        for cluster_id, chars in cluster_characteristics.items():
            if chars['volatility'] > 3:  # نوسان شدید
                regime = 3
            elif chars['adx'] > 25:  # روند قوی
                regime = 0 if chars['trend'] > 0 else 1
            else:  # رنج
                regime = 2

            cluster_to_regime[cluster_id] = regime

        # تبدیل cluster labels به regime labels
        regimes = [cluster_to_regime[cluster_id] for cluster_id in clusters]
        return regimes

    # ========== تحلیل نتایج ==========

    def generate_report(self, regimes: List[int], probabilities: pd.DataFrame = None) -> Dict:
        """تولید گزارش تحلیلی رژیم‌های بازار"""
        regime_counts = pd.Series(regimes).value_counts().sort_index()

        report = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'current_regime': self.regimes[regimes[-1]],
            'regime_distribution': {
                self.regimes[i]: int(regime_counts.get(i, 0))
                for i in range(4)
            },
            'regime_percentages': {
                self.regimes[i]: f"{100 * regime_counts.get(i, 0) / len(regimes):.1f}%"
                for i in range(4)
            }
        }

        # اگر احتمالات وجود داشت
        if probabilities is not None and len(probabilities) > 0:
            current_probs = probabilities.iloc[-1]
            report['current_probabilities'] = {
                self.regimes[i]: f"{current_probs.iloc[i]*100:.1f}%"
                for i in range(len(current_probs))
            }

        return report

def generate_sample_ohlcv(days: int = 100) -> pd.DataFrame:
    """تولید داده‌های نمونهٔ OHLCV برای تست"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # شبیه‌سازی قیمت‌های واقع‌گرایانه
    prices = []
    price = 100
    for _ in range(days):
        daily_return = np.random.normal(0.0005, 0.02)
        price *= (1 + daily_return)
        prices.append(price)

    df = pd.DataFrame({
        'Date': dates,
        'Open': [p * (1 + np.random.normal(0, 0.005)) for p in prices],
        'High': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'Low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, days)
    })

    df.set_index('Date', inplace=True)
    return df

def run_demo():
    """تست سیستم"""
    print("🎯 سیستم تشخیص رژیم بازار\n")

    # تولید داده‌ها
    ohlcv = generate_sample_ohlcv(days=100)
    print(f"✅ {len(ohlcv)} روز داده تولید شد\n")

    # تشخیص رژیم
    detector = MarketRegimeDetector()

    # استخراج ویژگی‌ها
    features = detector.extract_features(ohlcv)
    print(f"✅ ویژگی‌ها محاسبه شدند\n")

    # روش 1: Rule-Based
    print("=" * 60)
    print("📊 روش 1: Rule-Based (قواعین ساده)")
    print("=" * 60)
    rb_regimes, _ = detector.detect_regime_rule_based(features)
    rb_report = detector.generate_report(rb_regimes)
    print(f"رژیم فعلی: {rb_report['current_regime']}")
    print(f"توزیع رژیم‌ها:")
    for regime_name, count in rb_report['regime_distribution'].items():
        percentage = rb_report['regime_percentages'][regime_name]
        print(f"  {regime_name}: {count} روز ({percentage})")

    # روش 2: Clustering
    print("\n" + "=" * 60)
    print("📊 روش 2: Clustering (K-Means)")
    print("=" * 60)
    cl_regimes, cl_df = detector.detect_regime_clustering(features)
    cl_report = detector.generate_report(cl_regimes)
    print(f"رژیم فعلی: {cl_report['current_regime']}")
    print(f"توزیع رژیم‌ها:")
    for regime_name, count in cl_report['regime_distribution'].items():
        percentage = cl_report['regime_percentages'][regime_name]
        print(f"  {regime_name}: {count} روز ({percentage})")

    print("\n✅ سیستم آماده است!")

if __name__ == "__main__":
    run_demo()
