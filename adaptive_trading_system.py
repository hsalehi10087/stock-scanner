#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم معاملاتی تطبیق‌پذیر (Adaptive Trading System)
انتخاب خودکار استراتژی‌ها بر اساس رژیم بازار
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from market_regime_detector import MarketRegimeDetector

class TradingStrategy:
    """استراتژی معاملاتی پایه"""

    def __init__(self, name: str):
        self.name = name
        self.signals = []

    def generate_signal(self, features: pd.DataFrame) -> List[int]:
        """تولید سیگنال (1=خرید، -1=فروش، 0=بدون عمل)"""
        raise NotImplementedError

    def get_position_size(self, confidence: float) -> float:
        """محاسبهٔ اندازهٔ پوزیشن بر اساس اعتماد"""
        return min(1.0, confidence)


class TrendFollowingStrategy(TradingStrategy):
    """استراتژی دنبال‌کننده روند (Trend Following)
    بهترین برای: رژیم صعودی و نزولی قوی
    """

    def __init__(self):
        super().__init__("📈 دنبال‌کننده روند")

    def generate_signal(self, features: pd.DataFrame) -> List[int]:
        """
        منطق:
        - اگر ADX > 25 و Trend > 0 → خرید
        - اگر ADX > 25 و Trend < 0 → فروش
        - وگرنه: بدون عمل
        """
        signals = []

        for i in range(len(features)):
            adx = features.iloc[i].get('adx_14', 0)
            trend = features.iloc[i].get('trend_strength_20', 0)

            if adx > 25:
                signal = 1 if trend > 0 else -1
            else:
                signal = 0

            signals.append(signal)

        return signals

    def get_description(self) -> str:
        return """
🔥 دنبال‌کننده روند
━━━━━━━━━━━━━━━━━━
✅ بهترین برای: روند صعودی / روند نزولی قوی
❌ بدترین برای: بازار رنج (Whipsaw)

منطق:
- خرید در روندهای صعودی قوی (ADX > 25)
- فروش در روندهای نزولی قوی
- ریسک: کاهش سرمایه در بازار رنج

مثال:
ADX=30, Trend=+2 → خرید قوی ✅
ADX=15, Trend=-1 → بدون عمل (منتظر روند قوی)
        """


class MeanReversionStrategy(TradingStrategy):
    """استراتژی بازگشت به میانگین (Mean Reversion)
    بهترین برای: بازار رنج
    """

    def __init__(self):
        super().__init__("🔄 بازگشت به میانگین")

    def generate_signal(self, features: pd.DataFrame) -> List[int]:
        """
        منطق:
        - اگر ADX < 20 (بازار رنج):
            - اگر قیمت به پایین Bollinger Band → خرید
            - اگر قیمت به بالای Bollinger Band → فروش
        - وگرنه: بدون عمل
        """
        signals = []
        close = features.index

        for i in range(len(features)):
            adx = features.iloc[i].get('adx_14', 0)
            return_5d = features.iloc[i].get('return_5d', 0)

            if adx < 20:  # بازار رنج
                if return_5d < -3:  # سقوط - خرید
                    signal = 1
                elif return_5d > 3:  # صعود - فروش
                    signal = -1
                else:
                    signal = 0
            else:
                signal = 0

            signals.append(signal)

        return signals

    def get_description(self) -> str:
        return """
🔄 بازگشت به میانگین
━━━━━━━━━━━━━━━━━━
✅ بهترین برای: بازار رنج (Sideways)
❌ بدترین برای: روند‌های قوی (Trend Reversal Risk)

منطق:
- خرید در سقوط‌های ناگهانی (Return < -3%)
- فروش در صعود‌های شدید (Return > +3%)
- ریسک: تلفات بزرگ در روند‌های قوی

مثال:
ADX=15, Return=-4% → خرید قوی ✅
ADX=30, Return=+2% → بدون عمل (اجازه به روند)
        """


class CrisisManagementStrategy(TradingStrategy):
    """استراتژی مدیریت بحران (Risk-Off)
    برای: نوسان شدید / بحران
    """

    def __init__(self):
        super().__init__("⚡ مدیریت بحران")

    def generate_signal(self, features: pd.DataFrame) -> List[int]:
        """
        منطق:
        - اگر Volatility > 2x میانگین یا ATR > 2x میانگین:
            - خروج از بازار یا کاهش شدید حجم
        """
        signals = []

        volatility_20d = features['volatility_20d']
        volatility_mean = volatility_20d.rolling(window=30).mean()

        for i in range(len(features)):
            vol = features.iloc[i].get('volatility_20d', 0)
            vol_avg = volatility_mean.iloc[i]

            if vol > 2 * vol_avg:
                signal = -1  # خروج فوری
            else:
                signal = 0

            signals.append(signal)

        return signals

    def get_description(self) -> str:
        return """
⚡ مدیریت بحران
━━━━━━━━━━━━━━━━━━
✅ بهترین برای: نوسان شدید / بحران / پنیک‌سل
❌ بدترین برای: شرایط عادی (کاهش درآمد)

منطق:
- خروج فوری در نوسانات شدید
- کاهش شدید حجم معاملات
- منتظر بازگشت به شرایط عادی

مثال:
Volatility=5%, Avg=2% → خروج فوری ❌
Volatility=1.5%, Avg=2% → نرمال - ادامهٔ استراتژی
        """


class AdaptiveTradingSystem:
    """سیستم معاملاتی تطبیق‌پذیر

    معماری:
    ┌─────────────────┐
    │  داده OHLCV    │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ محاسبهٔ ویژگی  │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │تشخیص رژیم بازار│
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │  انتخاب استراتژی│
    │   (Strategy Mix)│
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │تخصیص سرمایه    │
    │(Capital Alloc.) │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │  سیگنال نهایی   │
    └─────────────────┘
    """

    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.strategies = {
            0: TrendFollowingStrategy(),      # صعودی
            1: TrendFollowingStrategy(),      # نزولی
            2: MeanReversionStrategy(),       # رنج
            3: CrisisManagementStrategy()     # بحران
        }
        self.regime_names = [
            "🔥 روند صعودی قوی",
            "❄️ روند نزولی قوی",
            "🔄 بازار رنج",
            "⚡ نوسان شدید"
        ]

    def allocate_capital(self, regimes: List[int], probabilities: pd.DataFrame = None) -> Dict[int, float]:
        """
        تخصیص سرمایه به استراتژی‌های مختلف بر اساس احتمالات رژیم

        Parameters:
        -----------
        regimes: لیست رژیم‌های شناسایی‌شده
        probabilities: احتمالات رژیم (از HMM)

        Returns:
        --------
        {استراتژی_id: وزن_سرمایه}
        """
        if probabilities is not None and len(probabilities) > 0:
            # استفاده از احتمالات (HMM approach)
            current_probs = probabilities.iloc[-1].values
            allocation = {
                i: max(0, current_probs[i])
                for i in range(4)
            }
        else:
            # استفاده از رژیم فعلی فقط
            current_regime = regimes[-1]
            allocation = {i: 1.0 if i == current_regime else 0.0 for i in range(4)}

        # نرمال‌سازی تا جمع = 1
        total = sum(allocation.values())
        if total > 0:
            allocation = {k: v/total for k, v in allocation.items()}

        return allocation

    def generate_adaptive_signals(self, ohlcv: pd.DataFrame,
                                  use_probabilities: bool = False) -> Dict:
        """
        تولید سیگنال‌های تطبیق‌پذیر

        Parameters:
        -----------
        ohlcv: داده‌های OHLCV
        use_probabilities: استفاده از احتمالات (HMM) برای تخصیص وزنی

        Returns:
        --------
        {
            'regime': رژیم فعلی,
            'allocation': {strategy: weight},
            'signals': {strategy: signal},
            'final_signal': سیگنال ترکیبی,
            'confidence': میزان اطمینان
        }
        """
        # مرحلهٔ 1: محاسبهٔ ویژگی‌ها
        features = self.regime_detector.extract_features(ohlcv)

        # مرحلهٔ 2: تشخیص رژیم
        regimes, _ = self.regime_detector.detect_regime_rule_based(features)
        current_regime = regimes[-1]

        # مرحلهٔ 3: تخصیص سرمایه
        allocation = self.allocate_capital(regimes)

        # مرحلهٔ 4: تولید سیگنال‌های هر استراتژی
        strategy_signals = {}
        final_signal = 0

        for strategy_id, strategy in self.strategies.items():
            signals = strategy.generate_signal(features)
            current_signal = signals[-1]
            weight = allocation[strategy_id]

            strategy_signals[strategy_id] = {
                'name': strategy.name,
                'signal': current_signal,
                'weight': weight,
                'weighted_signal': current_signal * weight
            }

            final_signal += current_signal * weight

        # محاسبهٔ اطمینان
        confidence = abs(final_signal)

        return {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'current_regime': self.regime_names[current_regime],
            'regime_id': current_regime,
            'allocation': allocation,
            'strategy_signals': strategy_signals,
            'final_signal': final_signal,
            'confidence': confidence,
            'decision': self._interpret_signal(final_signal)
        }

    def _interpret_signal(self, signal: float) -> str:
        """تفسیر سیگنال نهایی"""
        if signal > 0.5:
            return "🟢 خرید قوی"
        elif signal > 0.2:
            return "🟡 خرید ضعیف"
        elif signal < -0.5:
            return "🔴 فروش قوی"
        elif signal < -0.2:
            return "🟠 فروش ضعیف"
        else:
            return "⚪ بدون عمل"

    def print_report(self, analysis: Dict):
        """چاپ گزارش تفصیلی"""
        print(f"\n{'='*70}")
        print(f"📊 سیستم معاملاتی تطبیق‌پذیر")
        print(f"{'='*70}")
        print(f"⏰ {analysis['timestamp']}")
        print(f"\n🎯 رژیم فعلی: {analysis['current_regime']}")
        print(f"\n💰 تخصیص سرمایه:")
        for strategy_id, weight in analysis['allocation'].items():
            print(f"   {self.strategies[strategy_id].name}: {weight*100:.1f}%")

        print(f"\n📈 سیگنال‌های استراتژی:")
        for strategy_id, sig_info in analysis['strategy_signals'].items():
            signal_str = "✅ خرید" if sig_info['signal'] > 0 else "❌ فروش" if sig_info['signal'] < 0 else "⚪ بدون عمل"
            print(f"   {sig_info['name']}: {signal_str} (وزن: {sig_info['weight']*100:.1f}%)")

        print(f"\n🎲 سیگنال نهایی: {analysis['final_signal']:.2f}")
        print(f"📊 اطمینان: {analysis['confidence']*100:.1f}%")
        print(f"💡 تصمیم: {analysis['decision']}")
        print(f"{'='*70}\n")

    def print_strategy_descriptions(self):
        """چاپ توضیح استراتژی‌ها"""
        print("\n" + "="*70)
        print("📚 راهنمای استراتژی‌های معاملاتی")
        print("="*70)

        for strategy in self.strategies.values():
            print(strategy.get_description())

def run_demo():
    """تست سیستم"""
    from market_regime_detector import generate_sample_ohlcv

    print("\n🚀 راه‌اندازی سیستم معاملاتی تطبیق‌پذیر\n")

    # تولید داده‌ها
    ohlcv = generate_sample_ohlcv(days=100)

    # ایجاد سیستم
    system = AdaptiveTradingSystem()

    # تولید سیگنال‌های تطبیق‌پذیر
    analysis = system.generate_adaptive_signals(ohlcv)

    # چاپ گزارش
    system.print_report(analysis)

    # چاپ توضیح استراتژی‌ها
    system.print_strategy_descriptions()

if __name__ == "__main__":
    run_demo()
