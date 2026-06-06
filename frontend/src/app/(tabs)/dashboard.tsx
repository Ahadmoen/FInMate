import RisingStarCard from "@/components/dashboard/RisingStarCard";
import LivePriceUpdated from "@/components/ui/LivePriceUpdated";
import ScreenHeader from "@/components/ui/ScreenHeader";
import { setRisingStarsFromDashboard } from "@/navigation/risingStarsNavigation";
import { formatDayChangePct } from "@/utils/livePrice";
import { formatHealthLabel, formatOverallRisk } from "@/utils/portfolioMetrics";
import { useAuth } from "@/context/AuthContext";
import {
  type AIPickStock,
  type DashboardStocksResponse,
  type MarketIntelligence,
  type MarketMood,
  type NewsSentimentType,
  type NewsSentiment,
  type PortfolioHealth,
  type RisingStar,
  type SectorItem,
  type SectorSentiment,
  type SignalType,
  type TopPerformer,
  fetchDashboardNews,
  fetchDashboardStocks,
  mapToAIPick,
  mapToMarketIntelligence,
  mapToMarketMood,
  mapToPortfolioHealth,
  mapToRisingStars,
  mapToSectors,
  mapToTopPerformers,
} from "@/services/dashboard";
import { colors, fonts } from "@/styles/global";
import {
  Building2,
  ChevronRight,
  Landmark,
  LayoutDashboard,
  Monitor,
  ShoppingBag,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, G } from "react-native-svg";

// ─── Welcome Card ─────────────────────────────────────────────────────────────

function WelcomeCard() {
  return (
    <View style={styles.welcomeCard}>
      <Text style={styles.welcomeTitle}>Welcome to{"\n"}FinMate</Text>
      <Text style={styles.welcomeSub}>
        Your journey to financial independence starts here. Connect your
        accounts to get a holistic view of your wealth, or explore
        top-performing assets below.
      </Text>
      <Pressable style={styles.addPortfolioBtn}>
        <LayoutDashboard size={15} color={colors.primary} strokeWidth={2} />
        <Text style={styles.addPortfolioBtnText}>Add a portfolio</Text>
      </Pressable>
    </View>
  );
}

// ─── Portfolio summary card ────────────────────────────────────────────────────

/** Acrylic tints derived from colors.bgPrimaryLight (#EAF2F5) */
const ACRYLIC_FILL = "rgba(234, 242, 245, 0.22)";
const ACRYLIC_BORDER = "rgba(234, 242, 245, 0.38)";
const PANEL_ACRYLIC = "rgba(255, 255, 255, 0.1)";
const PANEL_ACRYLIC_BORDER = "rgba(234, 242, 245, 0.22)";

const P_LABEL = 10;
const P_VALUE_MD = 15;
const P_SCORE = 22;
const P_VALUE_XL = 30;

const fmtRs = (n: number) =>
  `Rs. ${n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function HealthScoreOrb({ score }: { score: number }) {
  const size = 68;
  const stroke = 5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, score));
  const filled = (pct / 100) * circumference;
  const orbSize = size - stroke * 2 - 4;

  return (
    <View style={[styles.pScoreOrbWrap, { width: size, height: size }]}>
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <G rotation="-90" origin={`${size / 2}, ${size / 2}`}>
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="rgba(255, 255, 255, 0.22)"
            strokeWidth={stroke}
            fill="none"
          />
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={colors.background}
            strokeWidth={stroke}
            fill="none"
            strokeDasharray={`${filled} ${circumference - filled}`}
            strokeLinecap="round"
          />
        </G>
      </Svg>
      <View
        style={[
          styles.pScoreOrb,
          {
            width: orbSize,
            height: orbSize,
            borderRadius: orbSize / 2,
          },
        ]}
      >
        <Text style={styles.pHealthScore}>{score}</Text>
      </View>
    </View>
  );
}

function PortfolioGridItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.pGridItem}>
      <Text style={styles.pGridLabel}>{label}</Text>
      <Text style={styles.pGridValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

function PortfolioHealthCard({
  data,
  onPress,
}: {
  data: PortfolioHealth;
  onPress?: () => void;
}) {
  const score = Math.max(0, Math.min(100, Math.round(data.score)));
  const divScore = Math.max(0, Math.min(10, data.diversificationScore));

  const change = data.changePercent;
  const isPositive = (change ?? 0) >= 0;
  const changeLabel = formatDayChangePct(change, { decimals: 2, suffix: "Today" });

  const holdingsValue =
    data.totalHoldings === 1
      ? "1 Asset"
      : `${data.totalHoldings} Assets`;

  const diversificationValue = `${data.diversificationLabel} (${divScore.toFixed(1)})`;

  return (
    <Pressable
      style={styles.pCard}
      onPress={onPress}
      disabled={!onPress}
    >
      <View style={styles.pCardSheen} pointerEvents="none" />

      <Text style={styles.pEyebrow}>Total portfolio value</Text>
      <Text style={styles.pHeroValue}>{fmtRs(data.totalValue)}</Text>

      <View style={styles.pChangeRow}>
        {isPositive ? (
          <TrendingUp size={14} color={colors.background} strokeWidth={2.5} />
        ) : (
          <TrendingDown size={14} color={colors.background} strokeWidth={2.5} />
        )}
        <Text style={styles.pChangeText}>{changeLabel}</Text>
      </View>

      <View style={styles.pHealthPanel}>
        <HealthScoreOrb score={score} />
        <View style={styles.pHealthCopy}>
          <Text style={styles.pEyebrow}>Portfolio Health</Text>
          <Text style={styles.pHealthStatus}>{formatHealthLabel(data.status)}</Text>
        </View>
      </View>

      <View style={styles.pDivider} />

      <View style={styles.pBottomRow}>
        <View style={styles.pGrid}>
          <View style={styles.pGridCol}>
            <PortfolioGridItem
              label="Overall Risk"
              value={formatOverallRisk(data.riskLevel)}
            />
            <PortfolioGridItem label="Total Holdings" value={holdingsValue} />
          </View>
          <View style={styles.pGridColRight}>
            <PortfolioGridItem
              label="Diversification"
              value={diversificationValue}
            />
          </View>
        </View>
        {onPress ? (
          <View style={styles.pNavBtn}>
            <ChevronRight size={18} color={colors.background} strokeWidth={2.2} />
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────

type SectionHeaderProps = {
  title: string;
  subtitle?: string;
  rightContent?: React.ReactNode;
};

function SectionHeader({ title, subtitle, rightContent }: SectionHeaderProps) {
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionHeaderTextCol}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle ? (
          <Text style={styles.sectionSubtitle}>{subtitle}</Text>
        ) : null}
      </View>
      {rightContent}
    </View>
  );
}

// ─── Signal config ────────────────────────────────────────────────────────────

const SIGNAL_CONFIG: Record<SignalType, { text: string; bg: string }> = {
  BULLISH: { text: "#16A34A", bg: "#DCFCE7" },
  NEUTRAL: { text: "#D97706", bg: "#FEF3C7" },
  BEARISH: { text: "#DC2626", bg: "#FEE2E2" },
};

// ─── Featured Hero Card (first Top Performer) ─────────────────────────────────

type StockNavPayload = {
  ticker: string;
  company: string;
  sector: string;
  price: number;
  changePercent: number | null;
  signal: SignalType;
  signalLabel?: string;
  sentiment?: string;
  rsi?: number;
};

function FeaturedStockCard({
  data,
  onIconPress,
}: {
  data: TopPerformer;
  onIconPress: () => void;
}) {
  const currency = data.currency ?? "Rs.";
  const sig = SIGNAL_CONFIG[data.signal];
  const change = data.changePercent;
  const isPositive = (change ?? 0) >= 0;
  const todayColor =
    change != null ? (isPositive ? "#16A34A" : "#DC2626") : colors.mutedText;
  const todayLabel = formatDayChangePct(change, {
    suffix: "Today",
    decimals: 1,
  });

  return (
    <View style={styles.featuredCard}>
      {/* Row 1: Ticker badge + company + signal pill */}
      <View style={styles.featuredTopRow}>
        <View style={styles.featuredTopLeft}>
          <View style={styles.featuredTickerBadge}>
            <Text style={styles.featuredTickerText}>{data.ticker}</Text>
          </View>
          <Text style={styles.featuredCompany}>{data.company}</Text>
        </View>
        {/* Solid green pill on dark bg */}
        <View style={[styles.signalPill, { backgroundColor: "#16A34A" }]}>
          <Text style={[styles.signalPillText, { color: "#FFFFFF" }]}>
            {data.signal}
          </Text>
        </View>
      </View>

      {/* Row 2: Price + forecast column */}
      <View style={styles.featuredPriceRow}>
        <View style={styles.featuredPriceCol}>
          <Text style={styles.featuredPrice}>
            {currency}{" "}
            {data.price.toLocaleString("en-PK", { minimumFractionDigits: 2 })}
          </Text>
          <View style={styles.featuredTodayRow}>
            {change != null ? (
              isPositive ? (
                <TrendingUp size={13} color={todayColor} strokeWidth={2.5} />
              ) : (
                <TrendingDown size={13} color={todayColor} strokeWidth={2.5} />
              )
            ) : null}
            <Text style={[styles.featuredTodayText, { color: todayColor }]}>
              {todayLabel}
            </Text>
          </View>
        </View>
        {data.forecast != null && Number.isFinite(data.forecast) && (
          <View style={styles.forecastCol}>
            <Text style={styles.forecastLabel}>MODEL FORECAST</Text>
            <Text style={styles.forecastValue}>
              {data.forecast >= 0 ? "+" : ""}
              {data.forecast.toFixed(1)}%
            </Text>
            <Text style={styles.forecastHint}>Predicted move</Text>
          </View>
        )}
      </View>

      {/* Divider — white on dark background */}
      <View style={styles.featuredDivider} />

      {/* Row 3: Signal dots + label | Sentiment */}
      <View style={styles.featuredBottomRow}>
        <View style={styles.signalDotsRow}>
          <View style={[styles.signalDot, { backgroundColor: "#4ADE80" }]} />
          <View style={[styles.signalDot, { backgroundColor: "#4ADE80" }]} />
          <View style={[styles.signalDot, { backgroundColor: "#4ADE80" }]} />
          <View style={[styles.signalDot, { backgroundColor: "#4ADE80" }]} />
          <Text style={styles.signalLabelText}>
            SIGNAL: {data.signalLabel ?? data.signal}
          </Text>
        </View>
        {data.sentiment ? (
          <Text style={styles.sentimentLabel}>
            Sentiment:{" "}
            <Text style={styles.sentimentValue}>{data.sentiment}</Text>
          </Text>
        ) : null}
      </View>

      <LivePriceUpdated
        at={data.priceUpdatedAt}
        variant="onPrimary"
        onPress={onIconPress}
      />
    </View>
  );
}

// ─── Compact Stock Card (remaining Top Performers) ────────────────────────────

function CompactStockCard({
  data,
  onIconPress,
}: {
  data: TopPerformer;
  onIconPress: () => void;
}) {
  const currency = data.currency ?? "Rs.";
  const sig = SIGNAL_CONFIG[data.signal];
  const change = data.changePercent;
  const isPositive = (change ?? 0) >= 0;
  const changeColor =
    change != null ? (isPositive ? "#16A34A" : "#DC2626") : colors.mutedText;
  const changeLabel = formatDayChangePct(change, { decimals: 1 });

  return (
    <View style={styles.compactCard}>
      <View style={styles.compactCardMain}>
        <View style={styles.compactTickerBadge}>
          <Text style={styles.compactTickerText}>{data.ticker}</Text>
        </View>

        <View style={styles.compactMid}>
          <Text style={styles.compactCompany}>{data.company}</Text>
          <View style={styles.compactMetaRow}>
            <View style={[styles.signalPill, { backgroundColor: sig.bg }]}>
              <Text style={[styles.signalPillText, { color: sig.text }]}>
                {data.signal}
              </Text>
            </View>
            <Text style={styles.compactRsi}>RSI: {data.rsi}</Text>
          </View>
        </View>

        <View style={styles.compactRight}>
          <Text style={styles.compactPrice}>
            {currency}{" "}
            {data.price.toLocaleString("en-PK", { minimumFractionDigits: 0 })}
          </Text>
          <Text style={[styles.compactChange, { color: changeColor }]}>
            {changeLabel}
          </Text>
        </View>
      </View>

      <LivePriceUpdated at={data.priceUpdatedAt} onPress={onIconPress} />
    </View>
  );
}

// ─── Top Performers Section ───────────────────────────────────────────────────

function TopPerformersSection({
  data,
  onStockPress,
}: {
  data: TopPerformer[];
  onStockPress: (stock: TopPerformer) => void;
}) {
  if (data.length === 0) return null;
  const [featured, ...rest] = data;

  return (
    <View style={styles.looseSectionWrapper}>
      <SectionHeader
        title="Top Performers"
        rightContent={<Text style={styles.realtimeLabel}>REAL-TIME</Text>}
      />
      <FeaturedStockCard
        data={featured}
        onIconPress={() => onStockPress(featured)}
      />
      {rest.map((stock) => (
        <CompactStockCard
          key={stock.ticker}
          data={stock}
          onIconPress={() => onStockPress(stock)}
        />
      ))}
    </View>
  );
}

// ─── Rising Stars Section ─────────────────────────────────────────────────────

function RisingStarsSection({
  data,
  onStockPress,
  onViewAllPress,
  showViewAll,
}: {
  data: RisingStar[];
  onStockPress: (stock: RisingStar) => void;
  onViewAllPress: () => void;
  showViewAll: boolean;
}) {
  return (
    <View style={styles.looseSectionWrapper}>
      <SectionHeader
        title="Rising Stars"
        rightContent={
          showViewAll ? (
            <Pressable
              style={styles.viewAllBtn}
              hitSlop={8}
              onPress={onViewAllPress}
            >
              <Text style={styles.viewAllText}>VIEW ALL</Text>
              <ChevronRight
                size={13}
                color={colors.primary}
                strokeWidth={2.2}
              />
            </Pressable>
          ) : undefined
        }
      />
      {/* Break out of parent's horizontal padding so cards scroll edge-to-edge */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.risingScroll}
        contentContainerStyle={styles.risingScrollContent}
      >
        {data.map((star) => (
          <RisingStarCard
            key={star.ticker}
            data={star}
            onIconPress={() => onStockPress(star)}
          />
        ))}
      </ScrollView>
    </View>
  );
}

// ─── AI Pick of the Day ───────────────────────────────────────────────────────

function AIPickSection({
  data,
  onIconPress,
}: {
  data: AIPickStock;
  onIconPress: () => void;
}) {
  const currency = data.currency ?? "Rs.";
  const change = data.changePercent;
  const isPositive = (change ?? 0) >= 0;
  const changeColor =
    change != null ? (isPositive ? "#16A34A" : "#DC2626") : colors.mutedText;
  const changeBg =
    change != null ? (isPositive ? "#DCFCE7" : "#FEE2E2") : colors.bgLight;
  const changeLabel = formatDayChangePct(change, { decimals: 1 });

  const signalLabel =
    data.signal === "BULLISH"
      ? "Bullish"
      : data.signal === "NEUTRAL"
        ? "Neutral"
        : data.signal === "BEARISH"
          ? "Bearish"
          : null;

  return (
    <View style={styles.looseSectionWrapper}>
      {/* Section header */}
      <SectionHeader
        title="AI Pick of the Day"
        rightContent={
          <Sparkles size={18} color={colors.primary} strokeWidth={1.6} />
        }
      />

      {/* Card */}
      <View style={styles.aiPickCard}>
        {/* TOP PICK corner badge */}
        {data.badge && (
          <View style={styles.aiPickCornerBadge}>
            <Text style={styles.aiPickCornerText}>{data.badge}</Text>
          </View>
        )}

        {/* Company row: ticker icon + name + sector */}
        <View style={styles.aiPickCompanyRow}>
          <View style={styles.aiPickTickerIcon}>
            <Text style={styles.aiPickTickerIconText}>{data.ticker}</Text>
          </View>
          <View style={styles.aiPickCompanyInfo}>
            <Text style={styles.aiPickCompanyName}>{data.companyName}</Text>
            <Text style={styles.aiPickSector}>{data.sector}</Text>
          </View>
        </View>

        {/* Price + change badge */}
        <View style={styles.aiPickPriceRow}>
          <Text style={styles.aiPickPrice}>
            {currency}{" "}
            {data.price.toLocaleString("en-PK", { minimumFractionDigits: 2 })}
          </Text>
          <View
            style={[styles.aiPickChangePill, { backgroundColor: changeBg }]}
          >
            <Text style={[styles.aiPickChangeText, { color: changeColor }]}>
              {changeLabel}
            </Text>
          </View>
        </View>

        {/* Chips: Forecast · Signal · RSI */}
        <View style={styles.aiPickChipsRow}>
          {data.forecast !== undefined && (
            <View style={styles.aiPickChip}>
              <View
                style={[styles.aiPickChipDot, { backgroundColor: "#16A34A" }]}
              />
              <Text style={styles.aiPickChipText}>
                Model forecast {data.forecast >= 0 ? "+" : ""}
                {data.forecast.toFixed(1)}%
              </Text>
            </View>
          )}
          {signalLabel && (
            <View style={styles.aiPickChip}>
              <View
                style={[styles.aiPickChipDot, { backgroundColor: "#16A34A" }]}
              />
              <Text style={styles.aiPickChipText}>{signalLabel}</Text>
            </View>
          )}
          {data.rsi !== undefined && (
            <View style={styles.aiPickChip}>
              <View
                style={[styles.aiPickChipDot, { backgroundColor: "#2563EB" }]}
              />
              <Text style={styles.aiPickChipText}>RSI {data.rsi}</Text>
            </View>
          )}
        </View>

        {/* Divider */}
        <View style={styles.rowDivider} />

        {/* Italic analyst quote */}
        {data.description && (
          <Text style={styles.aiPickQuote}>"{data.description}"</Text>
        )}

        <LivePriceUpdated at={data.priceUpdatedAt} onPress={onIconPress} />
      </View>
    </View>
  );
}

// ─── Market Mood Section ──────────────────────────────────────────────────────

const CONFIDENCE_ZONES = ["FEAR", "NEUTRAL", "CONFIDENT", "GREEDY"] as const;

function getActiveZone(idx: number) {
  if (idx <= 25) return "FEAR";
  if (idx <= 50) return "NEUTRAL";
  if (idx <= 75) return "CONFIDENT";
  return "GREEDY";
}

const NEWS_SENTIMENT_STYLE: Record<
  NewsSentimentType,
  { color: string; bg: string; border: string }
> = {
  Positive: { color: "#16A34A", bg: "#F0FDF4", border: "#16A34A" },
  Neutral: { color: "#D97706", bg: "#FFFBEB", border: "#D97706" },
  Negative: { color: "#DC2626", bg: "#FEF2F2", border: "#DC2626" },
};

function MarketMoodSection({ data }: { data: MarketMood }) {
  const activeZone = getActiveZone(data.confidenceIndex);
  const newsSty = NEWS_SENTIMENT_STYLE[data.newsSentiment];

  return (
    <View style={styles.looseSectionWrapper}>
      <SectionHeader
        title="Market Mood"
        rightContent={
          <View style={styles.moodLiveRow}>
            <View style={styles.moodLiveDot} />
            <Text style={styles.moodTodayLabel}>Today</Text>
          </View>
        }
      />

      {/* ── Card ── */}
      <View style={[styles.card, styles.moodCard]}>
        {/* Row 1: Sentiment + Score */}
        <View style={styles.moodTopRow}>
          <View style={styles.moodTopLeft}>
            <Text style={styles.moodSentimentBig}>{data.sentiment}</Text>
            <Text style={styles.moodCaptionText}>{data.caption}</Text>
          </View>
          <View style={styles.moodScoreCol}>
            <Text style={styles.moodScoreNum}>{data.score}</Text>
            <Text style={styles.moodScoreNote}>
              OF {data.totalStocks} STOCKS{"\n"}BULLISH
            </Text>
          </View>
        </View>

        {/* Tri-color bar */}
        <View style={styles.moodTriBar}>
          <View
            style={[
              styles.moodTriSeg,
              { flex: data.bullCount, backgroundColor: "#16A34A" },
            ]}
          />
          <View
            style={[
              styles.moodTriSeg,
              { flex: data.neutralCount, backgroundColor: "#F59E0B" },
            ]}
          />
          <View
            style={[
              styles.moodTriSeg,
              { flex: data.bearCount, backgroundColor: "#DC2626" },
            ]}
          />
        </View>

        {/* Legend */}
        <View style={styles.moodLegendRow}>
          {[
            { count: data.bullCount, label: "bullish", color: "#16A34A" },
            { count: data.neutralCount, label: "neutral", color: "#F59E0B" },
            { count: data.bearCount, label: "bearish", color: "#DC2626" },
          ].map(({ count, label, color }) => (
            <View key={label} style={styles.moodLegendItem}>
              <View
                style={[styles.moodLegendDot, { backgroundColor: color }]}
              />
              <Text style={styles.moodLegendText}>
                {count} {label}
              </Text>
            </View>
          ))}
        </View>

        <View style={styles.rowDivider} />

        {/* Signal Breakdown | News Sentiment */}
        <View style={styles.moodMidRow}>
          <View style={styles.moodSignalCol}>
            <Text style={styles.moodSubLabel}>SIGNAL BREAKDOWN</Text>
            <Text style={styles.moodSignalBase}>
              <Text style={styles.moodSignalBuy}>{data.buySignals} Buy </Text>
              <Text style={styles.moodSignalHold}>
                {data.holdSignals} Hold{" "}
              </Text>
              <Text style={styles.moodSignalSell}>{data.sellSignals} Sell</Text>
            </Text>
          </View>

          <View style={styles.moodVertDivider} />

          <View style={styles.moodNewsCol}>
            <Text style={styles.moodSubLabel}>NEWS SENTIMENT</Text>
            <View
              style={[
                styles.moodNewsPill,
                { backgroundColor: newsSty.bg, borderColor: newsSty.border },
              ]}
            >
              <Text style={[styles.moodNewsPillText, { color: newsSty.color }]}>
                {data.newsSentiment}
              </Text>
            </View>
            <Text style={styles.moodNewsNote}>
              Dominant across {data.newsSentimentPercent}% of{"\n"}stocks
            </Text>
          </View>
        </View>

        <View style={styles.rowDivider} />

        {/* Market Confidence Index */}
        <View style={styles.moodConfSection}>
          <View style={styles.moodConfHeaderRow}>
            <Text style={styles.moodSubLabel}>MARKET CONFIDENCE INDEX</Text>
            <Text style={styles.moodConfScore}>
              {data.confidenceIndex} / 100
            </Text>
          </View>

          <View style={styles.moodConfTrackWrapper}>
            <View style={styles.moodConfTrack}>
              <View
                style={[styles.moodConfFill, { flex: data.confidenceIndex }]}
              />
              <View
                style={[
                  styles.moodConfEmpty,
                  { flex: 100 - data.confidenceIndex },
                ]}
              />
            </View>
            <View
              style={[
                styles.moodConfThumb,
                { left: `${data.confidenceIndex}%` as any },
              ]}
            />
          </View>

          <View style={styles.moodConfLabels}>
            {CONFIDENCE_ZONES.map((zone) => (
              <Text
                key={zone}
                style={[
                  styles.moodConfLabel,
                  zone === activeZone && styles.moodConfLabelActive,
                ]}
              >
                {zone}
              </Text>
            ))}
          </View>
        </View>

        <View style={styles.rowDivider} />

        {/* Hottest Sector + Updated */}
        <View style={styles.moodFooterRow}>
          <View style={styles.moodFooterLeft}>
            <Text style={styles.moodSubLabel}>HOTTEST SECTOR</Text>
            <View style={styles.moodSectorChip}>
              <Text style={styles.moodSectorChipText}>
                {data.hottestSector}
              </Text>
            </View>
          </View>
        </View>
        <Text style={styles.moodUpdatedText}>Updated {data.updatedAt}</Text>
      </View>
    </View>
  );
}

// ─── Sector Performance Section ───────────────────────────────────────────────

type LucideIcon = React.ComponentType<{
  size?: number;
  color?: string;
  strokeWidth?: number;
}>;

const SECTOR_ICON_MAP: Record<string, LucideIcon> = {
  monitor: Monitor,
  landmark: Landmark,
  building: Building2,
  zap: Zap,
  shopping: ShoppingBag,
};

const SECTOR_SENTIMENT_STYLE: Record<
  SectorSentiment,
  { text: string; bg: string }
> = {
  Bullish: { text: "#FFFFFF", bg: "#16A34A" },
  Neutral: { text: "#FFFFFF", bg: "#D97706" },
  Bearish: { text: "#FFFFFF", bg: "#DC2626" },
};

function SectorCard({ data }: { data: SectorItem }) {
  const isPositive = data.avgForecast >= 0;
  const forecastColor = isPositive ? colors.primary : "#DC2626";
  const changeBg = isPositive ? "#DCFCE7" : "#FEE2E2";
  const changeText = isPositive ? "#16A34A" : "#DC2626";
  const changeLabel = `${isPositive ? "+" : ""}${data.avgForecast.toFixed(1)}%`;
  const sentSty = SECTOR_SENTIMENT_STYLE[data.sentiment];
  const total = data.buyCount + data.holdCount + data.sellCount;
  const IconComp = SECTOR_ICON_MAP[data.iconKey] ?? Monitor;

  return (
    <View style={styles.sectorCard}>
      {/* Row 1: icon badge + change pill */}
      <View style={styles.sectorTopRow}>
        <View style={styles.sectorIconBadge}>
          <IconComp size={20} color={colors.text} strokeWidth={1.6} />
        </View>
        <View style={[styles.sectorChangePill, { backgroundColor: changeBg }]}>
          <Text style={[styles.sectorChangePillText, { color: changeText }]}>
            {changeLabel}
          </Text>
        </View>
      </View>

      {/* Name + stock count */}
      <View style={styles.sectorNameBlock}>
        <Text style={styles.sectorName}>{data.name}</Text>
        <Text style={styles.sectorStockCount}>{data.stockCount} stocks</Text>
      </View>

      {/* Forecast row */}
      <View style={styles.sectorForecastRow}>
        <Text style={[styles.sectorForecastValue, { color: forecastColor }]}>
          {changeLabel}
        </Text>
        <Text style={styles.sectorForecastLabel}> avg forecast</Text>
      </View>

      {/* Signal tri-color bar */}
      <View style={styles.sectorSignalBar}>
        <View
          style={[
            styles.sectorSignalSeg,
            { flex: data.buyCount, backgroundColor: "#16A34A" },
          ]}
        />
        <View
          style={[
            styles.sectorSignalSeg,
            { flex: data.holdCount, backgroundColor: "#F59E0B" },
          ]}
        />
        <View
          style={[
            styles.sectorSignalSeg,
            { flex: data.sellCount, backgroundColor: "#DC2626" },
          ]}
        />
      </View>

      {/* Signal counts */}
      <View style={styles.sectorSignalCounts}>
        <Text style={[styles.sectorSignalCount, { color: "#16A34A" }]}>
          {data.buyCount} BUY
        </Text>
        <Text style={[styles.sectorSignalCount, { color: "#F59E0B" }]}>
          {data.holdCount} HOLD
        </Text>
        <Text style={[styles.sectorSignalCount, { color: "#DC2626" }]}>
          {data.sellCount} SELL
        </Text>
      </View>

      {/* Bottom: sentiment pill + HOTTEST */}
      <View style={styles.sectorBottomRow}>
        <View
          style={[styles.sectorSentimentPill, { backgroundColor: sentSty.bg }]}
        >
          <Text style={[styles.sectorSentimentText, { color: sentSty.text }]}>
            {data.sentiment}
          </Text>
        </View>
        {data.isHottest && (
          <Text style={styles.sectorHottestLabel}>HOTTEST</Text>
        )}
      </View>
    </View>
  );
}

function SectorPerformanceSection({ data }: { data: SectorItem[] }) {
  return (
    <View style={styles.looseSectionWrapper}>
      <SectionHeader
        title="Sector Performance"
        subtitle="Ranked by average health score"
      />

      {/* Horizontal scroll — breaks out of parent padding */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.risingScroll}
        contentContainerStyle={styles.risingScrollContent}
      >
        {data.map((sector) => (
          <SectorCard key={sector.id} data={sector} />
        ))}
      </ScrollView>
    </View>
  );
}

// ─── Sentiment Badge ──────────────────────────────────────────────────────────

function SentimentBadge({ sentiment }: { sentiment: NewsSentiment }) {
  const config = {
    POSITIVE: { color: "#16A34A", bg: "#DCFCE7", label: "POSITIVE" },
    NEUTRAL: { color: "#D97706", bg: "#FEF3C7", label: "NEUTRAL" },
    NEGATIVE: { color: "#DC2626", bg: "#FEE2E2", label: "NEGATIVE" },
  }[sentiment];

  return (
    <View style={[styles.sentimentBadge, { backgroundColor: config.bg }]}>
      <Text style={[styles.sentimentText, { color: config.color }]}>
        {config.label}
      </Text>
    </View>
  );
}

// ─── Market Intelligence Section ──────────────────────────────────────────────

function MarketIntelligenceSection({
  data,
  onViewAllPress,
}: {
  data: MarketIntelligence;
  onViewAllPress?: () => void;
}) {
  return (
    <View style={styles.looseSectionWrapper}>
      <SectionHeader
        title="Market Intelligence"
        rightContent={
          <Pressable
            style={styles.viewAllBtn}
            hitSlop={8}
            onPress={onViewAllPress}
          >
            <Text style={styles.viewAllText}>View All News</Text>
            <ChevronRight size={13} color={colors.primary} strokeWidth={2.2} />
          </Pressable>
        }
      />
      {data.news.map((item) => (
        <Pressable key={item.id} style={styles.newsCard}>
          <SentimentBadge sentiment={item.sentiment} />
          <Text style={styles.newsTitle} numberOfLines={3}>
            {item.title}
          </Text>
          <Text style={styles.newsMeta}>
            {item.source} <Text style={styles.newsTime}>{item.timeAgo}</Text>
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

// ─── Skeleton Loaders ─────────────────────────────────────────────────────────

function SectionCardSkeleton({ height = 150 }: { height?: number }) {
  return (
    <View style={[styles.card, styles.skeletonCard, { height }]}>
      <ActivityIndicator size="small" color={colors.primary} />
    </View>
  );
}

function ScrollSectionSkeleton({ title }: { title: string }) {
  return (
    <View style={styles.looseSectionWrapper}>
      <SectionHeader title={title} />
      <View style={styles.skeletonScrollRow}>
        {([0, 1] as const).map((i) => (
          <View key={i} style={[styles.card, styles.skeletonScrollCard]}>
            <ActivityIndicator size="small" color={colors.primary} />
          </View>
        ))}
      </View>
    </View>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────────

function signalToParam(signal: SignalType): string {
  if (signal === "BULLISH") return "BUY";
  if (signal === "BEARISH") return "SELL";
  return "HOLD";
}

export default function DashboardScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { token } = useAuth();

  const openStockInsight = useCallback(
    (stock: StockNavPayload) => {
      router.push({
        pathname: "/stock-insight/[ticker]",
        params: {
          ticker: stock.ticker,
          company_name: stock.company,
          sector: stock.sector,
          close: String(stock.price),
          change_pct:
            stock.changePercent != null ? String(stock.changePercent) : "",
          signal: signalToParam(stock.signal),
          signal_label: stock.signalLabel ?? stock.signal,
          health_display: stock.sentiment ?? "",
          confidence_display: "",
          rsi14: stock.rsi != null ? String(stock.rsi) : "",
        },
      });
    },
    [router],
  );

  const [stocksData, setStocksData] = useState<DashboardStocksResponse | null>(
    null,
  );
  const [marketNews, setMarketNews] = useState<MarketIntelligence | null>(null);
  const [stocksLoading, setStocksLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const mappedData = useMemo(() => {
    if (!stocksData) return null;
    const allRisingStars = mapToRisingStars(stocksData);
    return {
      portfolioHealth: stocksData.portfolio_health
        ? mapToPortfolioHealth(stocksData.portfolio_health)
        : null,
      topPerformers: mapToTopPerformers(stocksData),
      risingStars: allRisingStars.slice(0, 5),
      risingStarsRest: allRisingStars.slice(5),
      aiPick: mapToAIPick(stocksData),
      marketMood: mapToMarketMood(stocksData),
      sectors: mapToSectors(stocksData),
    };
  }, [stocksData]);

  const loadDashboard = useCallback(
    async (isRefresh = false) => {
      if (!token) return;
      if (isRefresh) setRefreshing(true);
      else {
        setStocksLoading(true);
        setNewsLoading(true);
      }
      try {
        const [stocks, news] = await Promise.all([
          fetchDashboardStocks(token),
          fetchDashboardNews(token),
        ]);
        setStocksData(stocks);
        setMarketNews(mapToMarketIntelligence(news));
      } catch {
        /* keep prior data */
      } finally {
        setStocksLoading(false);
        setNewsLoading(false);
        setRefreshing(false);
      }
    },
    [token],
  );

  useFocusEffect(
    useCallback(() => {
      void loadDashboard();
    }, [loadDashboard]),
  );

  const isLoading = stocksLoading && !refreshing && !mappedData;

  return (
    <View style={styles.safe}>
      <View style={[styles.headerArea, { paddingTop: insets.top }]}>
        <ScreenHeader />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => loadDashboard(true)}
            tintColor={colors.primary}
          />
        }
      >
        {isLoading ? (
          <SectionCardSkeleton height={300} />
        ) : mappedData.portfolioHealth ? (
          <PortfolioHealthCard
            data={mappedData.portfolioHealth}
            onPress={() => router.push("/(tabs)/portfolio")}
          />
        ) : (
          <WelcomeCard />
        )}

        {/* ── Top Performers ── */}
        {isLoading ? (
          <SectionCardSkeleton height={320} />
        ) : (
          <TopPerformersSection
            data={mappedData.topPerformers}
            onStockPress={openStockInsight}
          />
        )}

        {/* ── Rising Stars ── */}
        {isLoading ? (
          <ScrollSectionSkeleton title="Rising Stars" />
        ) : (
          <RisingStarsSection
            data={mappedData.risingStars}
            showViewAll={mappedData.risingStarsRest.length > 0}
            onViewAllPress={() => {
              setRisingStarsFromDashboard(mappedData.risingStarsRest);
              router.push("/(tabs)/rising-stars");
            }}
            onStockPress={(star) =>
              openStockInsight({
                ticker: star.ticker,
                company: star.company,
                sector: star.sector,
                price: star.price,
                changePercent: star.changePercent,
                signal: star.signal,
                signalLabel: star.signalLabel,
                sentiment: star.sentimentLabel,
              })
            }
          />
        )}

        {/* ── AI Pick of the Day ── */}
        {isLoading ? (
          <SectionCardSkeleton height={280} />
        ) : mappedData.aiPick ? (
          <AIPickSection
            data={mappedData.aiPick}
            onIconPress={() =>
              openStockInsight({
                ticker: mappedData.aiPick!.ticker,
                company: mappedData.aiPick!.companyName,
                sector: mappedData.aiPick!.sector ?? "",
                price: mappedData.aiPick!.price,
                changePercent: mappedData.aiPick!.changePercent,
                signal: mappedData.aiPick!.signal ?? "NEUTRAL",
                rsi: mappedData.aiPick!.rsi,
              })
            }
          />
        ) : null}

        {/* ── Market Mood ── */}
        {isLoading ? (
          <SectionCardSkeleton height={400} />
        ) : (
          <MarketMoodSection data={mappedData.marketMood} />
        )}

        {/* ── Sector Performance ── */}
        {isLoading ? (
          <ScrollSectionSkeleton title="Sector Performance" />
        ) : (
          <SectorPerformanceSection data={mappedData.sectors} />
        )}

        {newsLoading || !marketNews ? (
          <SectionCardSkeleton height={280} />
        ) : (
          <MarketIntelligenceSection
            data={marketNews}
            onViewAllPress={() => router.push("/(tabs)/news")}
          />
        )}

        <View style={styles.bottomSpacer} />
      </ScrollView>
    </View>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bgLight },
  headerArea: { backgroundColor: colors.background },

  // ── Scroll
  scroll: { flex: 1, backgroundColor: colors.bgLight },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    gap: 14,
  },
  bottomSpacer: { height: 16 },

  // ── Shared card shell
  card: {
    backgroundColor: colors.background,
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },

  // ── Section wrapper (no border/bg, for grid sections)
  looseSectionWrapper: {
    gap: 10,
  },

  // ── Section header (matches Sector Performance)
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: 2,
  },
  sectionHeaderTextCol: {
    flex: 1,
    gap: 3,
    paddingRight: 8,
  },
  sectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 22,
    color: colors.text,
    letterSpacing: -0.5,
  },
  sectionSubtitle: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },

  // ── Real-time plain label
  realtimeLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: colors.mutedText,
    letterSpacing: 0.5,
  },

  // ── Row divider (inside cards)
  rowDivider: {
    height: 1,
    backgroundColor: colors.borderLight,
  },

  // ── Card grid (2-column)
  cardGrid: {
    flexDirection: "row",
    gap: 10,
  },
  cardGridGhost: { flex: 1 },

  // ── View all button
  viewAllBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingTop: 4,
  },
  viewAllText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.primary,
  },

  // ── Welcome Card
  welcomeCard: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: 22,
  },
  welcomeTitle: {
    fontFamily: fonts.heading,
    fontSize: 30,
    color: "#FFFFFF",
    letterSpacing: -1,
    lineHeight: 36,
    marginBottom: 12,
  },
  welcomeSub: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: "rgba(255,255,255,0.72)",
    lineHeight: 20,
    marginBottom: 20,
  },
  addPortfolioBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "rgba(255,255,255,0.93)",
    borderRadius: 10,
    paddingVertical: 11,
    paddingHorizontal: 16,
    alignSelf: "flex-start",
  },
  addPortfolioBtnText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.primary,
  },

  // ── Portfolio summary card
  pCard: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: 18,
    overflow: "hidden",
  },
  pCardSheen: {
    position: "absolute",
    top: -60,
    right: -40,
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: colors.bgPrimaryLight,
    opacity: 0.28,
  },
  pEyebrow: {
    fontFamily: fonts.bodyMedium,
    fontSize: P_LABEL,
    color: colors.bgTertiaryLight,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  pHeroValue: {
    fontFamily: fonts.heading,
    fontSize: P_VALUE_XL,
    color: colors.background,
    letterSpacing: -0.6,
    lineHeight: 34,
    marginTop: 4,
    marginBottom: 4,
  },
  pChangeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 14,
  },
  pChangeText: {
    fontFamily: fonts.bodyMedium,
    fontSize: P_LABEL,
    color: colors.background,
  },
  pHealthPanel: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: PANEL_ACRYLIC,
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: PANEL_ACRYLIC_BORDER,
  },
  pScoreOrbWrap: {
    alignItems: "center",
    justifyContent: "center",
  },
  pScoreOrb: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: ACRYLIC_FILL,
    borderWidth: 1,
    borderColor: ACRYLIC_BORDER,
  },
  pHealthScore: {
    fontFamily: fonts.heading,
    fontSize: P_SCORE,
    color: colors.background,
    letterSpacing: -0.4,
  },
  pHealthCopy: {
    flex: 1,
    gap: 4,
    justifyContent: "center",
  },
  pHealthStatus: {
    fontFamily: fonts.heading,
    fontSize: P_VALUE_MD,
    color: colors.background,
    letterSpacing: -0.3,
  },
  pDivider: {
    height: 1,
    backgroundColor: colors.themeMedium,
    marginTop: 16,
    marginBottom: 14,
  },
  pBottomRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 12,
  },
  pGrid: {
    flex: 1,
    flexDirection: "row",
    gap: 20,
  },
  pGridCol: {
    flex: 1,
    gap: 16,
  },
  pGridColRight: {
    flex: 1,
    justifyContent: "flex-start",
  },
  pGridItem: {
    gap: 5,
  },
  pGridLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: P_LABEL,
    color: colors.bgTertiaryLight,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  pGridValue: {
    fontFamily: fonts.heading,
    fontSize: P_VALUE_MD,
    color: colors.background,
    letterSpacing: -0.2,
    lineHeight: 20,
  },
  pNavBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: colors.themeMedium,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2,
  },

  // ── Signal pill (shared: featured + compact)
  signalPill: {
    alignSelf: "flex-start",
    paddingHorizontal: 9,
    paddingVertical: 3,
    borderRadius: 20,
  },
  signalPillText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.3,
  },

  // ── Rising Stars horizontal scroll
  risingScroll: {
    marginHorizontal: -16,
  },
  risingScrollContent: {
    paddingHorizontal: 16,
    gap: 12,
    paddingBottom: 2,
  },

  // ── Featured hero card (dark primary background)
  featuredCard: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: 16,
    gap: 12,
  },
  featuredTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  featuredTopLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  featuredTickerBadge: {
    backgroundColor: "rgba(255,255,255,0.18)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 7,
  },
  featuredTickerText: {
    fontFamily: fonts.heading,
    fontSize: 12,
    color: "#FFFFFF",
    letterSpacing: 0.4,
  },
  featuredCompany: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: "#FFFFFF",
  },
  featuredPriceRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  featuredPriceCol: {
    gap: 6,
  },
  featuredPrice: {
    fontFamily: fonts.heading,
    fontSize: 28,
    color: "#FFFFFF",
    letterSpacing: -1,
  },
  featuredTodayRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  featuredTodayText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
  },
  forecastCol: {
    alignItems: "flex-end",
    gap: 2,
    paddingTop: 2,
  },
  forecastLabel: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: "rgba(255,255,255,0.6)",
    letterSpacing: 0.5,
  },
  forecastValue: {
    fontFamily: fonts.heading,
    fontSize: 18,
    color: "#4ADE80",
    letterSpacing: -0.5,
  },
  forecastHint: {
    fontFamily: fonts.body,
    fontSize: 9,
    color: "rgba(255,255,255,0.5)",
    letterSpacing: 0.2,
  },
  featuredDivider: {
    height: 1,
    backgroundColor: "rgba(255,255,255,0.18)",
  },
  featuredBottomRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  signalDotsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  signalDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  signalLabelText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: "rgba(255,255,255,0.9)",
    letterSpacing: 0.2,
    marginLeft: 2,
  },
  sentimentLabel: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: "rgba(255,255,255,0.6)",
  },
  sentimentValue: {
    fontFamily: fonts.bodyMedium,
    color: "#4ADE80",
  },

  // ── Compact stock card
  compactCard: {
    backgroundColor: colors.background,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 6,
  },
  compactCardMain: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  compactTickerBadge: {
    width: 52,
    height: 36,
    borderRadius: 9,
    backgroundColor: colors.bgLight,
    alignItems: "center",
    justifyContent: "center",
  },
  compactTickerText: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: colors.text,
    letterSpacing: 0.3,
  },
  compactMid: {
    flex: 1,
    gap: 5,
  },
  compactCompany: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: colors.text,
  },
  compactMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
  },
  compactRsi: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },
  compactRight: {
    alignItems: "flex-end",
    gap: 3,
  },
  compactPrice: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
  },
  compactChange: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
  },

  // ── AI Pick of the Day
  aiPickCard: {
    backgroundColor: colors.background,
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 14,
    overflow: "hidden",
  },
  aiPickCornerBadge: {
    position: "absolute",
    top: 0,
    right: 0,
    backgroundColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderBottomLeftRadius: 12,
    borderTopRightRadius: 16,
  },
  aiPickCornerText: {
    fontFamily: fonts.heading,
    fontSize: 10,
    color: "#FFFFFF",
    letterSpacing: 0.6,
  },
  aiPickCompanyRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 8,
  },
  aiPickTickerIcon: {
    width: 52,
    height: 52,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  aiPickTickerIconText: {
    fontFamily: fonts.heading,
    fontSize: 13,
    color: "#FFFFFF",
    letterSpacing: 0.4,
  },
  aiPickCompanyInfo: {
    gap: 3,
  },
  aiPickCompanyName: {
    fontFamily: fonts.heading,
    fontSize: 18,
    color: colors.text,
    letterSpacing: -0.3,
  },
  aiPickSector: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
  },
  aiPickPriceRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  aiPickPrice: {
    fontFamily: fonts.heading,
    fontSize: 28,
    color: colors.text,
    letterSpacing: -1,
  },
  aiPickChangePill: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 20,
  },
  aiPickChangeText: {
    fontFamily: fonts.heading,
    fontSize: 13,
  },
  aiPickChipsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  aiPickChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.bgLight,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  aiPickChipDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  aiPickChipText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.text,
  },
  aiPickQuote: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
    lineHeight: 20,
    fontStyle: "italic",
  },

  // ── Market Mood
  moodCard: {
    gap: 12,
  },
  moodLiveRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingTop: 4,
  },
  moodLiveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#16A34A",
  },
  moodTodayLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.mutedText,
    letterSpacing: 0.2,
  },
  moodTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  moodTopLeft: {
    flex: 1,
    gap: 4,
  },
  moodSentimentBig: {
    fontFamily: fonts.heading,
    fontSize: 26,
    color: colors.text,
    letterSpacing: -0.8,
  },
  moodCaptionText: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  moodScoreCol: {
    alignItems: "flex-end",
    gap: 1,
  },
  moodScoreNum: {
    fontFamily: fonts.heading,
    fontSize: 26,
    color: colors.text,
    letterSpacing: -1,
  },
  moodScoreNote: {
    fontFamily: fonts.body,
    fontSize: 9,
    color: colors.mutedText,
    textAlign: "right",
    letterSpacing: 0.3,
    lineHeight: 12,
  },
  moodTriBar: {
    flexDirection: "row",
    height: 6,
    borderRadius: 3,
    overflow: "hidden",
  },
  moodTriSeg: {
    height: "100%",
  },
  moodLegendRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  moodLegendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  moodLegendDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  moodLegendText: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.text,
  },
  moodMidRow: {
    flexDirection: "row",
  },
  moodSignalCol: {
    flex: 1,
    gap: 8,
  },
  moodVertDivider: {
    width: 1,
    backgroundColor: colors.borderLight,
    marginHorizontal: 14,
  },
  moodNewsCol: {
    flex: 1,
    gap: 7,
  },
  moodSubLabel: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    color: colors.mutedText,
    letterSpacing: 0.5,
  },
  moodSignalBase: {
    fontSize: 14,
  },
  moodSignalBuy: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: "#16A34A",
  },
  moodSignalHold: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: "#F59E0B",
  },
  moodSignalSell: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: "#DC2626",
  },
  moodNewsPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
  },
  moodNewsPillEmoji: {
    fontSize: 13,
  },
  moodNewsPillText: {
    fontFamily: fonts.heading,
    fontSize: 13,
  },
  moodNewsNote: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
    lineHeight: 16,
  },
  moodConfSection: {
    gap: 10,
  },
  moodConfHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  moodConfScore: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
    letterSpacing: -0.3,
  },
  moodConfTrackWrapper: {
    position: "relative",
    height: 20,
    justifyContent: "center",
  },
  moodConfTrack: {
    flexDirection: "row",
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
  },
  moodConfFill: {
    backgroundColor: colors.primary,
  },
  moodConfEmpty: {
    backgroundColor: colors.bgLight,
  },
  moodConfThumb: {
    position: "absolute",
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.background,
    borderWidth: 3,
    borderColor: colors.primary,
    transform: [{ translateX: -9 }],
    top: 1,
  },
  moodConfLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  moodConfLabel: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.mutedText,
  },
  moodConfLabelActive: {
    fontFamily: fonts.heading,
    color: colors.text,
    fontSize: 10,
  },
  moodFooterRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  moodFooterLeft: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
  },
  moodSectorChip: {
    backgroundColor: colors.bgLight,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  moodSectorChipText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    color: colors.text,
  },
  moodUpdatedText: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },

  // ── Sector Card
  sectorCard: {
    width: 195,
    backgroundColor: colors.background,
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 10,
  },
  sectorTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  sectorIconBadge: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.bgLight,
    alignItems: "center",
    justifyContent: "center",
  },
  sectorChangePill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  sectorChangePillText: {
    fontFamily: fonts.heading,
    fontSize: 11,
  },
  sectorNameBlock: {
    gap: 2,
  },
  sectorName: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.3,
  },
  sectorStockCount: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  sectorForecastRow: {
    flexDirection: "row",
    alignItems: "baseline",
  },
  sectorForecastValue: {
    fontFamily: fonts.heading,
    fontSize: 18,
    letterSpacing: -0.5,
  },
  sectorForecastLabel: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.mutedText,
  },
  sectorSignalBar: {
    flexDirection: "row",
    height: 5,
    borderRadius: 3,
    overflow: "hidden",
  },
  sectorSignalSeg: {
    height: "100%",
  },
  sectorSignalCounts: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  sectorSignalCount: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.3,
  },
  sectorBottomRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectorSentimentPill: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
  },
  sectorSentimentText: {
    fontFamily: fonts.heading,
    fontSize: 12,
  },
  sectorHottestLabel: {
    fontFamily: fonts.heading,
    fontSize: 11,
    color: colors.text,
    letterSpacing: 0.4,
  },

  // ── News Card
  newsCard: {
    backgroundColor: colors.background,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 8,
  },
  sentimentBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  sentimentText: {
    fontFamily: fonts.bodyMedium,
    fontSize: 10,
    letterSpacing: 0.6,
  },
  newsTitle: {
    fontFamily: fonts.heading,
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  newsMeta: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.mutedText,
  },
  newsTime: { color: colors.mutedText },

  // ── Skeleton loaders
  skeletonCard: {
    alignItems: "center",
    justifyContent: "center",
  },
  skeletonScrollRow: {
    flexDirection: "row",
    gap: 12,
  },
  skeletonScrollCard: {
    width: 220,
    height: 220,
    alignItems: "center",
    justifyContent: "center",
  },
});
