import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  Activity,
  BarChart3,
  Check,
  ChevronDown,
  CircleDollarSign,
  Clock,
  MessageCircle,
  Plus,
  RefreshCcw,
  Send,
  Share2,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
  User,
  Wifi,
  WifiOff,
  X
} from "lucide-react-native";
import { cloneElement, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentProps, Dispatch, ReactElement, SetStateAction } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  Share,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";

import {
  API_URL,
  addComment,
  createPost,
  createUser,
  feedWebSocketUrl,
  getBias,
  getUser,
  listComments,
  listPosts,
  predictOutcome,
  submitBiasFeedback,
  suggestUsernames,
  type BiasDirection,
  type BiasRead,
  type FeedMessage
} from "./src/api/coinfox";
import {
  buildPostShareUrl,
  buildReadShareUrl,
  currentWebUrl,
  parseCoinFoxDirectLink,
  type DirectLinkTarget
} from "./src/links";
import { TERMS } from "./src/terms";
import { colors, radii, shadow } from "./src/theme";
import type { Comment, Direction, PredictionOutcome, TradePost, TradePostDraft, User as Trader } from "./src/types";

const USER_ID_KEY = "coinfox.currentUserId";
const LEGACY_USER_ID_KEY = "nyfx.currentUserId";
const ANONYMOUS_ID_KEY = "coinfox.anonymousUserId";
const INITIAL_DRAFT: FormDraft = {
  symbol: "SPY",
  direction: "long",
  entry_price: "0",
  stop_loss: "0",
  take_profit: "0",
  reasoning: ""
};

const DISCLAIMER_FOOTER = "Not investment advice · CoinFox has no crypto coin or token";
const NO_TOKEN_DISCLAIMER =
  "CoinFox is a market-reading and idea-sharing app. It is NOT a cryptocurrency and has no coin, " +
  "token, ICO, or presale. In-app Gold is play-money for entertainment only — it has no cash value " +
  "and cannot be bought, sold, or withdrawn. CoinFox is not affiliated with any token using the names " +
  "CoinFox, FoxCoin, FoxClaw, or Eastern Pine. Treat any such token as a scam. Nothing here is " +
  "investment advice.";

type Screen = "read" | "desk" | "post" | "account";
type WsStatus = "idle" | "connected" | "disconnected";
type IconElement = ReactElement<{ color?: string }>;
type PositionSide = "flat" | Direction;
type AssetPreset = {
  symbol: string;
  label: string;
  category: string;
  why: string;
  drivers: string[];
  details: string[];
};
type FormDraft = {
  symbol: string;
  direction: Direction;
  entry_price: string;
  stop_loss: string;
  take_profit: string;
  reasoning: string;
};
type ThesisCheck = {
  label: string;
  value: string;
  note: string;
};

const MAJOR_ASSETS: AssetPreset[] = [
  {
    symbol: "SPY",
    label: "S&P 500",
    category: "Index",
    why: "Broad US risk appetite. If SPY is trending, single names usually feel it.",
    drivers: ["rates", "dollar", "mega-cap breadth"],
    details: ["premarket high/low", "VWAP reclaim", "sector breadth"]
  },
  {
    symbol: "QQQ",
    label: "Nasdaq",
    category: "Index",
    why: "Growth and AI beta. When QQQ moves, tech and crypto sentiment often move with it.",
    drivers: ["NVDA/MSFT/AAPL", "real yields", "VIX"],
    details: ["opening range", "relative strength vs SPY", "volume expansion"]
  },
  {
    symbol: "DIA",
    label: "Dow",
    category: "Index",
    why: "Old-economy tone. Helps separate broad market strength from pure tech chasing.",
    drivers: ["industrials", "energy", "financials"],
    details: ["breadth", "failed breakouts", "defensive rotation"]
  },
  {
    symbol: "IWM",
    label: "Russell",
    category: "Index",
    why: "Small-cap risk thermometer. Useful for spotting whether risk appetite is real.",
    drivers: ["credit", "regional banks", "yields"],
    details: ["range acceptance", "relative strength", "liquidity pockets"]
  },
  {
    symbol: "NVDA",
    label: "Nvidia",
    category: "Mega cap",
    why: "AI risk leader. It can pull the whole growth complex around intraday.",
    drivers: ["semis", "QQQ", "AI headlines"],
    details: ["prior day high/low", "gamma levels", "failed momentum pushes"]
  },
  {
    symbol: "AAPL",
    label: "Apple",
    category: "Mega cap",
    why: "Mega-cap ballast. Weak Apple can cap index rallies even when other names run.",
    drivers: ["consumer tech", "China headlines", "QQQ/SPY weight"],
    details: ["trendline holds", "volume dries", "support shelf"]
  },
  {
    symbol: "BTCUSDT",
    label: "Bitcoin",
    category: "Crypto",
    why: "Global liquidity and risk pulse. Trades 24/7, often moves before cash markets open.",
    drivers: ["dollar", "rates", "ETF flows"],
    details: ["funding", "spot premium", "liquidation levels"]
  },
  {
    symbol: "DXY",
    label: "Dollar",
    category: "Macro",
    why: "Liquidity pressure gauge. A rising dollar can pressure risk assets and commodities.",
    drivers: ["Fed path", "global growth", "safe haven flows"],
    details: ["breakout retests", "yield confirmation", "risk-asset divergence"]
  },
  {
    symbol: "US10Y",
    label: "10Y yield",
    category: "Rates",
    why: "Discount-rate anchor. Growth stocks often care deeply about the 10-year.",
    drivers: ["inflation data", "auction demand", "Fed speakers"],
    details: ["basis-point impulse", "real yield move", "equity reaction lag"]
  },
  {
    symbol: "GC",
    label: "Gold",
    category: "Commodity",
    why: "Fear, real rates, and dollar cross-current. Useful when risk signals conflict.",
    drivers: ["real yields", "DXY", "geopolitical stress"],
    details: ["COMEX range", "dollar divergence", "safe-haven bid"]
  },
  {
    symbol: "CL",
    label: "Oil",
    category: "Commodity",
    why: "Inflation and growth input. Oil shocks can ripple into rates, transports, and risk.",
    drivers: ["OPEC", "inventory data", "geopolitics"],
    details: ["inventory reaction", "trend day risk", "energy equity confirmation"]
  }
];

export default function App() {
  const [screen, setScreen] = useState<Screen>("read");
  const [userId, setUserId] = useState<string | null>(null);
  const [anonymousUserId, setAnonymousUserId] = useState<string | null>(null);
  const [trader, setTrader] = useState<Trader | null>(null);
  const [username, setUsername] = useState("");
  const [posts, setPosts] = useState<TradePost[]>([]);
  const [readSymbol, setReadSymbol] = useState("BTCUSDT");
  const [biasRead, setBiasRead] = useState<BiasRead | null>(null);
  const [biasLoading, setBiasLoading] = useState(false);
  const [biasError, setBiasError] = useState<string | null>(null);
  const [readPrice, setReadPrice] = useState("");
  const [positionSide, setPositionSide] = useState<PositionSide>("flat");
  const [positionEntry, setPositionEntry] = useState("");
  const [expandedPostId, setExpandedPostId] = useState<string | null>(null);
  const [commentsByPost, setCommentsByPost] = useState<Record<string, Comment[]>>({});
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<FormDraft>(INITIAL_DRAFT);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("idle");
  const websocketRef = useRef<WebSocket | null>(null);

  const currentStats = useMemo(() => {
    const open = posts.filter((post) => !post.resolved).length;
    const resolved = posts.length - open;
    const tp = posts.reduce((sum, post) => sum + (post.prediction_stats?.tp_predictions || 0), 0);
    const sl = posts.reduce((sum, post) => sum + (post.prediction_stats?.sl_predictions || 0), 0);
    return { open, resolved, tp, sl };
  }, [posts]);

  const refresh = useCallback(async (nextUserId = userId, quiet = false) => {
    if (!nextUserId) {
      setLoading(false);
      return;
    }
    try {
      if (!quiet) setRefreshing(true);
      const [freshUser, freshPosts] = await Promise.all([
        getUser(nextUserId),
        listPosts(nextUserId, 50)
      ]);
      setTrader(freshUser);
      setPosts(freshPosts);
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not reach the exchange");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [userId]);

  const refreshBias = useCallback(async (quiet = false) => {
    const symbol = readSymbol.trim().toUpperCase() || "BTCUSDT";
    try {
      if (!quiet) setBiasLoading(true);
      const nextRead = await getBias(symbol);
      setBiasRead(nextRead);
      setBiasError(null);
    } catch (error) {
      setBiasError(error instanceof Error ? error.message : "Could not load live bias");
    } finally {
      setBiasLoading(false);
    }
  }, [readSymbol]);

  const applyDirectLinkTarget = useCallback((target: DirectLinkTarget | null) => {
    if (!target) return;
    if (target.screen === "read") {
      setReadSymbol(target.symbol);
      setScreen("read");
      return;
    }
    setScreen("desk");
    if (target.postId) {
      setExpandedPostId(target.postId);
    }
  }, []);

  useEffect(() => {
    Promise.all([AsyncStorage.getItem(USER_ID_KEY), AsyncStorage.getItem(LEGACY_USER_ID_KEY)])
      .then(async ([storedUserId, legacyUserId]) => {
        const resolvedUserId = storedUserId || legacyUserId;
        if (legacyUserId && !storedUserId) {
          await AsyncStorage.setItem(USER_ID_KEY, legacyUserId);
        }
        if (resolvedUserId) {
          setUserId(resolvedUserId);
          void refresh(resolvedUserId, true);
        } else {
          setLoading(false);
        }
      })
      .catch(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    AsyncStorage.getItem(ANONYMOUS_ID_KEY)
      .then(async (storedId) => {
        if (storedId) {
          setAnonymousUserId(storedId);
          return;
        }
        const nextId = createAnonymousId();
        await AsyncStorage.setItem(ANONYMOUS_ID_KEY, nextId);
        setAnonymousUserId(nextId);
      })
      .catch(() => setAnonymousUserId(createAnonymousId()));
  }, []);

  useEffect(() => {
    let mounted = true;
    const applyUrl = (url: string | null) => {
      if (!mounted) return;
      applyDirectLinkTarget(parseCoinFoxDirectLink(url));
    };

    applyUrl(currentWebUrl());
    Linking.getInitialURL().then(applyUrl).catch(() => undefined);
    const subscription = Linking.addEventListener("url", (event) => applyUrl(event.url));

    return () => {
      mounted = false;
      subscription.remove();
    };
  }, [applyDirectLinkTarget]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void refreshBias();
    }, 250);
    return () => clearTimeout(timer);
  }, [refreshBias]);

  useEffect(() => {
    if (!expandedPostId || commentsByPost[expandedPostId]) return;
    listComments(expandedPostId)
      .then((comments) => setCommentsByPost((current) => ({ ...current, [expandedPostId]: comments })))
      .catch((error) => {
        setNotice(error instanceof Error ? error.message : "Could not load linked comments");
      });
  }, [commentsByPost, expandedPostId]);

  const shareDirectLink = useCallback(async (label: string, url: string) => {
    try {
      if (Platform.OS === "web") {
        const webNavigator = globalThis.navigator as {
          clipboard?: { writeText: (value: string) => Promise<void> };
          share?: (data: { title: string; text: string; url: string }) => Promise<void>;
        } | undefined;
        if (webNavigator?.share) {
          await webNavigator.share({ title: label, text: label, url });
          setNotice(`${label} link opened for sharing.`);
          return;
        }
        if (webNavigator?.clipboard?.writeText) {
          await webNavigator.clipboard.writeText(url);
          setNotice(`${label} link copied.`);
          return;
        }
      }

      await Share.share({
        title: label,
        message: `${label}: ${url}`,
        url
      });
      setNotice(`${label} link ready to share.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not share link");
    }
  }, []);

  const handleShareRead = useCallback(() => {
    const symbol = readSymbol.trim().toUpperCase() || "BTCUSDT";
    void shareDirectLink(`CoinFox ${symbol} read`, buildReadShareUrl(symbol));
  }, [readSymbol, shareDirectLink]);

  const handleSharePost = useCallback((post: TradePost) => {
    void shareDirectLink(`CoinFox ${post.symbol.toUpperCase()} setup`, buildPostShareUrl(post.id));
  }, [shareDirectLink]);

  useEffect(() => {
    if (!userId) return;

    const socket = new WebSocket(feedWebSocketUrl());
    websocketRef.current = socket;
    setWsStatus("disconnected");

    socket.onopen = () => {
      setWsStatus("connected");
      socket.send("ready");
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(String(event.data)) as FeedMessage;
        if (message.type === "new_post" || message.type === "new_prediction") {
          void refresh(userId, true);
        }
      } catch {
        void refresh(userId, true);
      }
    };
    socket.onerror = () => setWsStatus("disconnected");
    socket.onclose = () => setWsStatus("disconnected");

    return () => {
      websocketRef.current = null;
      socket.close();
    };
  }, [refresh, userId]);

  const handleSuggestName = async () => {
    try {
      const suggestions = await suggestUsernames(1);
      if (suggestions[0]) {
        setUsername(suggestions[0]);
        setNotice(null);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not fetch a name");
    }
  };

  const handleCreateUser = async () => {
    const handle = username.trim();
    if (!handle) {
      setNotice("Handle required");
      return;
    }
    setSubmitting(true);
    try {
      const nextUser = await createUser(handle);
      await AsyncStorage.setItem(USER_ID_KEY, nextUser.id);
      setUserId(nextUser.id);
      setTrader(nextUser);
      setUsername("");
      setNotice(null);
      await refresh(nextUser.id, true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not create trader");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSignOut = async () => {
    await AsyncStorage.removeItem(USER_ID_KEY);
    await AsyncStorage.removeItem(LEGACY_USER_ID_KEY);
    setUserId(null);
    setTrader(null);
    setPosts([]);
    setCommentsByPost({});
    setExpandedPostId(null);
    setScreen("account");
  };

  const handlePost = async () => {
    if (!userId) {
      setScreen("account");
      return;
    }
    const parsedDraft = parseDraft(draft);
    if (!parsedDraft) {
      setNotice("Entry, thesis check, and target must be positive numbers");
      return;
    }
    setSubmitting(true);
    try {
      await createPost(userId, parsedDraft);
      setDraft(INITIAL_DRAFT);
      setScreen("desk");
      await refresh(userId, true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not publish setup");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePrediction = async (postId: string, outcome: PredictionOutcome) => {
    if (!userId) {
      setScreen("account");
      return;
    }
    try {
      await predictOutcome(userId, postId, outcome);
      await refresh(userId, true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Prediction rejected");
    }
  };

  const handleBiasFeedback = async (action: string) => {
    if (!biasRead || !anonymousUserId) {
      setNotice("Live read is still loading.");
      return;
    }
    try {
      await submitBiasFeedback({
        anonymous_user_id: anonymousUserId,
        symbol: biasRead.symbol,
        bias_shown: biasRead.bias,
        confidence_shown: biasRead.confidence ?? biasRead.conviction ?? 0,
        user_action: action,
        user_invalidation_level: biasRead.invalidation?.level ?? null
      });
      setNotice(action === "thumbs_up" ? "Feedback saved. Glad this read helped." : "Feedback saved. CoinFox will include it in reports.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not save feedback");
    }
  };

  const toggleComments = async (postId: string) => {
    const next = expandedPostId === postId ? null : postId;
    setExpandedPostId(next);
    if (next && !commentsByPost[next]) {
      try {
        const comments = await listComments(next);
        setCommentsByPost((current) => ({ ...current, [next]: comments }));
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "Could not load comments");
      }
    }
  };

  const handleComment = async (postId: string) => {
    if (!userId) {
      setScreen("account");
      return;
    }
    const content = (commentDrafts[postId] || "").trim();
    if (!content) return;
    try {
      const saved = await addComment(userId, postId, content);
      setCommentsByPost((current) => ({
        ...current,
        [postId]: [...(current[postId] || []), saved]
      }));
      setCommentDrafts((current) => ({ ...current, [postId]: "" }));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Comment rejected");
    }
  };

  const body = () => {
    if (loading) {
      return (
        <View style={styles.centerPane}>
          <ActivityIndicator color={colors.green} />
        </View>
      );
    }

    if (!userId || !trader) {
      return (
        <AccountGate
          username={username}
          setUsername={setUsername}
          onCreate={handleCreateUser}
          onSuggestName={handleSuggestName}
          submitting={submitting}
          notice={notice}
        />
      );
    }

    if (screen === "read") {
      return (
        <ReadScreen
          symbol={readSymbol}
          setSymbol={setReadSymbol}
          currentPrice={readPrice}
          setCurrentPrice={setReadPrice}
          positionSide={positionSide}
          setPositionSide={setPositionSide}
          positionEntry={positionEntry}
          setPositionEntry={setPositionEntry}
          posts={posts}
          biasRead={biasRead}
          biasLoading={biasLoading}
          biasError={biasError}
          refreshing={refreshing}
          notice={notice}
          onRefresh={() => {
            void refresh(userId);
            void refreshBias();
          }}
          onShareRead={handleShareRead}
          onBiasFeedback={handleBiasFeedback}
        />
      );
    }

    if (screen === "post") {
      return (
        <PostScreen
          draft={draft}
          setDraft={setDraft}
          onSubmit={handlePost}
          submitting={submitting}
          notice={notice}
        />
      );
    }

    if (screen === "account") {
      return (
        <AccountScreen
          trader={trader}
          stats={currentStats}
          wsStatus={wsStatus}
          onRefresh={() => refresh(userId)}
          onSignOut={handleSignOut}
          refreshing={refreshing}
          notice={notice}
        />
      );
    }

    return (
      <DeskScreen
        trader={trader}
        posts={posts}
        stats={currentStats}
        wsStatus={wsStatus}
        refreshing={refreshing}
        notice={notice}
        expandedPostId={expandedPostId}
        commentsByPost={commentsByPost}
        commentDrafts={commentDrafts}
        setCommentDrafts={setCommentDrafts}
        onRefresh={() => refresh(userId)}
        onPredict={handlePrediction}
        onSharePost={handleSharePost}
        onToggleComments={toggleComments}
        onComment={handleComment}
      />
    );
  };

  return (
    <SafeAreaView style={styles.app}>
      <StatusBar barStyle="light-content" />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.keyboard}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.kicker}>New York Fox Exchange</Text>
            <Text style={styles.title}>Trading desk</Text>
          </View>
          <View style={[styles.connectionPill, wsStatus === "connected" ? styles.connected : styles.disconnected]}>
            {wsStatus === "connected" ? <Wifi size={14} color={colors.green} /> : <WifiOff size={14} color={colors.red} />}
            <Text style={styles.connectionText}>{wsStatus === "connected" ? "live" : "offline"}</Text>
          </View>
        </View>

        <View style={styles.disclaimerBar}>
          <ShieldCheck size={13} color={colors.dim} />
          <Text style={styles.disclaimerBarText}>{DISCLAIMER_FOOTER}</Text>
        </View>

        <View style={styles.content}>{body()}</View>

        {userId && trader ? (
          <View style={styles.tabBar}>
            <TabButton active={screen === "read"} label="Read" icon={<BarChart3 size={19} />} onPress={() => setScreen("read")} />
            <TabButton active={screen === "desk"} label="Desk" icon={<Activity size={19} />} onPress={() => setScreen("desk")} />
            <TabButton active={screen === "post"} label="Post" icon={<Plus size={19} />} onPress={() => setScreen("post")} />
            <TabButton active={screen === "account"} label="Account" icon={<User size={19} />} onPress={() => setScreen("account")} />
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function GoldChip({ amount, compact = false }: { amount: number; compact?: boolean }) {
  return (
    <View style={[styles.goldChip, compact ? styles.goldChipCompact : null]}>
      <CircleDollarSign size={compact ? 12 : 14} color={colors.amber} />
      <Text style={styles.goldChipText}>{amount.toLocaleString()}</Text>
    </View>
  );
}

function DisclaimerCard() {
  return (
    <View style={styles.disclaimerCard}>
      <View style={styles.disclaimerCardHeader}>
        <ShieldCheck size={16} color={colors.amber} />
        <Text style={styles.disclaimerCardTitle}>No coin. No token. Play-money only.</Text>
      </View>
      <Text style={styles.disclaimerCardText}>{NO_TOKEN_DISCLAIMER}</Text>
    </View>
  );
}

function AccountGate({
  username,
  setUsername,
  onCreate,
  onSuggestName,
  submitting,
  notice
}: {
  username: string;
  setUsername: (value: string) => void;
  onCreate: () => void;
  onSuggestName: () => void;
  submitting: boolean;
  notice: string | null;
}) {
  return (
    <View style={styles.accountGate}>
      <View style={styles.gateIcon}>
        <ShieldCheck size={34} color={colors.green} />
      </View>
      <Text style={styles.gateTitle}>Trader check-in</Text>
      <View style={styles.handleRow}>
        <Field
          label="Handle"
          value={username}
          onChangeText={setUsername}
          placeholder="StopLossStan"
          autoCapitalize="none"
          returnKeyType="done"
          onSubmitEditing={onCreate}
          containerStyle={styles.handleField}
        />
        <Pressable style={styles.diceButton} onPress={onSuggestName} accessibilityLabel="Suggest a name">
          <RefreshCcw size={18} color={colors.green} />
        </Pressable>
      </View>
      <Text style={styles.anonNote}>
        You're 100% anonymous. Pick a random market handle or make your own — share real details only if you choose to.
      </Text>
      <Pressable style={styles.primaryButton} onPress={onCreate} disabled={submitting}>
        {submitting ? <ActivityIndicator color={colors.bg} /> : <Check size={18} color={colors.bg} />}
        <Text style={styles.primaryButtonText}>Enter exchange</Text>
      </Pressable>
      {notice ? <Notice message={notice} /> : null}
      <DisclaimerCard />
    </View>
  );
}

function ReadScreen({
  symbol,
  setSymbol,
  currentPrice,
  setCurrentPrice,
  positionSide,
  setPositionSide,
  positionEntry,
  setPositionEntry,
  posts,
  biasRead,
  biasLoading,
  biasError,
  refreshing,
  notice,
  onRefresh,
  onShareRead,
  onBiasFeedback
}: {
  symbol: string;
  setSymbol: (value: string) => void;
  currentPrice: string;
  setCurrentPrice: (value: string) => void;
  positionSide: PositionSide;
  setPositionSide: (value: PositionSide) => void;
  positionEntry: string;
  setPositionEntry: (value: string) => void;
  posts: TradePost[];
  biasRead: BiasRead | null;
  biasLoading: boolean;
  biasError: string | null;
  refreshing: boolean;
  notice: string | null;
  onRefresh: () => void;
  onShareRead: () => void;
  onBiasFeedback: (action: string) => void;
}) {
  const [showThesisHelp, setShowThesisHelp] = useState(false);
  const read = useMemo(
    () => buildMarketRead(symbol, posts, parseOptionalNumber(currentPrice), positionSide, parseOptionalNumber(positionEntry), biasRead),
    [biasRead, currentPrice, positionEntry, positionSide, posts, symbol]
  );

  return (
    <ScrollView
      contentContainerStyle={styles.scrollContent}
      refreshControl={<RefreshControl tintColor={colors.green} refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View style={styles.readControls}>
        <Field
          label="Market"
          value={symbol}
          onChangeText={(value) => setSymbol(value.toUpperCase())}
          placeholder="SPY"
          containerStyle={styles.readControlField}
        />
        <Field
          label="Current price"
          value={currentPrice}
          onChangeText={setCurrentPrice}
          placeholder="Optional"
          keyboardType="decimal-pad"
          containerStyle={styles.readControlField}
        />
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.assetRail}
      >
        {MAJOR_ASSETS.map((asset) => (
          <AssetChip
            key={asset.symbol}
            asset={asset}
            active={read.symbol === asset.symbol}
            onPress={() => setSymbol(asset.symbol)}
          />
        ))}
      </ScrollView>

      <View style={styles.readPanel}>
        <View style={styles.readHeader}>
          <View>
            <Text style={styles.readLabel}>CoinFox bias</Text>
            <Text style={[styles.readAction, { color: read.accent }]}>{read.action}</Text>
          </View>
          <View style={styles.readHeaderActions}>
            <Pressable style={styles.iconGhostButton} onPress={onShareRead} accessibilityLabel="Share read link">
              <Share2 size={16} color={colors.text} />
            </Pressable>
            <View style={[styles.readBadge, { borderColor: read.accent }]}>
              <Text style={[styles.readBadgeText, { color: read.accent }]}>{read.symbol}</Text>
            </View>
          </View>
        </View>
        {biasLoading ? (
          <View style={styles.liveStateRow}>
            <ActivityIndicator color={colors.green} />
            <Text style={styles.liveStateText}>Loading live bias</Text>
          </View>
        ) : null}
        {biasError ? <Notice message={biasError} /> : null}
        <Text style={styles.readWhy}>{read.why}</Text>
        <ChanceMeter up={read.chanceUp} down={read.chanceDown} />
        <View style={styles.zoneBand}>
          <Target size={16} color={read.accent} />
          <Text style={styles.zoneText}>{read.zone}</Text>
        </View>
        <View style={styles.thesisCheckRow}>
          <View style={styles.thesisCheckCopy}>
            <Text style={styles.thesisCheckLabel}>{read.thesisCheck.label}</Text>
            <Text style={styles.thesisCheckValue}>{read.thesisCheck.value}</Text>
          </View>
          <Pressable style={styles.infoButton} onPress={() => setShowThesisHelp((current) => !current)}>
            <Text style={styles.infoButtonText}>?</Text>
          </Pressable>
        </View>
        {showThesisHelp ? (
          <Text style={styles.thesisHelp}>{read.thesisCheck.note} {TERMS["Thesis check"]}</Text>
        ) : null}
        {biasRead ? (
          <View style={styles.feedbackRow}>
            <Pressable style={styles.feedbackButton} onPress={() => onBiasFeedback("thumbs_up")}>
              <Check size={15} color={colors.green} />
              <Text style={styles.feedbackButtonText}>Useful</Text>
            </Pressable>
            <Pressable style={styles.feedbackButton} onPress={() => onBiasFeedback("disagree")}>
              <X size={15} color={colors.amber} />
              <Text style={styles.feedbackButtonText}>Disagree</Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      <View style={styles.sectionPanel}>
        <View style={styles.sectionHeader}>
          <Activity size={20} color={colors.green} />
          <Text style={styles.sectionTitle}>Overhead map</Text>
        </View>
        {read.overhead.map((row) => (
          <ContextLine key={row.label} {...row} />
        ))}
      </View>

      <View style={styles.sectionPanel}>
        <View style={styles.sectionHeader}>
          <Target size={20} color={colors.amber} />
          <Text style={styles.sectionTitle}>Micro details</Text>
        </View>
        {read.micro.map((row) => (
          <ContextLine key={row.label} {...row} />
        ))}
      </View>

      <View style={styles.sectionPanel}>
        <View style={styles.sectionHeader}>
          <BarChart3 size={20} color={colors.blue} />
          <Text style={styles.sectionTitle}>Indicator stack</Text>
        </View>
        {read.indicators.map((indicator) => (
          <IndicatorRow key={indicator.label} {...indicator} />
        ))}
      </View>

      <View style={styles.sectionPanel}>
        <View style={styles.sectionHeader}>
          <ShieldCheck size={20} color={colors.amber} />
          <Text style={styles.sectionTitle}>Position assist</Text>
        </View>
        <Text style={styles.fieldLabel}>Current position</Text>
        <View style={styles.segment}>
          <SegmentButton active={positionSide === "flat"} label="Flat" icon={<Activity size={16} />} onPress={() => setPositionSide("flat")} />
          <SegmentButton active={positionSide === "long"} label="Long" icon={<TrendingUp size={16} />} onPress={() => setPositionSide("long")} />
          <SegmentButton active={positionSide === "short"} label="Short" icon={<TrendingDown size={16} />} onPress={() => setPositionSide("short")} />
        </View>
        {positionSide !== "flat" ? (
          <Field
            label="Your entry"
            value={positionEntry}
            onChangeText={setPositionEntry}
            placeholder="Optional"
            keyboardType="decimal-pad"
          />
        ) : null}
        <View style={styles.assistBox}>
          <Text style={styles.assistTitle}>{read.positionTitle}</Text>
          <Text style={styles.assistText}>{read.positionNote}</Text>
        </View>
      </View>

      {notice ? <Notice message={notice} /> : null}
    </ScrollView>
  );
}

function DeskScreen({
  trader,
  posts,
  stats,
  wsStatus,
  refreshing,
  notice,
  expandedPostId,
  commentsByPost,
  commentDrafts,
  setCommentDrafts,
  onRefresh,
  onPredict,
  onSharePost,
  onToggleComments,
  onComment
}: {
  trader: Trader;
  posts: TradePost[];
  stats: { open: number; resolved: number; tp: number; sl: number };
  wsStatus: WsStatus;
  refreshing: boolean;
  notice: string | null;
  expandedPostId: string | null;
  commentsByPost: Record<string, Comment[]>;
  commentDrafts: Record<string, string>;
  setCommentDrafts: Dispatch<SetStateAction<Record<string, string>>>;
  onRefresh: () => void;
  onPredict: (postId: string, outcome: PredictionOutcome) => void;
  onSharePost: (post: TradePost) => void;
  onToggleComments: (postId: string) => void;
  onComment: (postId: string) => void;
}) {
  return (
    <ScrollView
      contentContainerStyle={styles.scrollContent}
      refreshControl={<RefreshControl tintColor={colors.green} refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View style={styles.scoreRow}>
        <MetricTile label="Gold" value={String(trader.gold)} accent={colors.amber} icon={<CircleDollarSign size={17} />} />
        <MetricTile label="Open" value={String(stats.open)} accent={colors.green} icon={<Activity size={17} />} />
        <MetricTile label="Resolved" value={String(stats.resolved)} accent={colors.blue} icon={<BarChart3 size={17} />} />
      </View>

      <View style={styles.marketStrip}>
        <Clock size={16} color={colors.amber} />
        <Text style={styles.marketStripText}>NY session</Text>
        <Text style={styles.marketStripMeta}>9:30 AM-4:00 PM ET</Text>
        {wsStatus === "connected" ? <Text style={styles.marketLive}>LIVE</Text> : null}
      </View>

      {notice ? <Notice message={notice} /> : null}

      {posts.length === 0 ? (
        <EmptyState />
      ) : (
        posts.map((post) => (
          <TradeCard
            key={post.id}
            post={post}
            expanded={expandedPostId === post.id}
            comments={commentsByPost[post.id] || []}
            commentDraft={commentDrafts[post.id] || ""}
            setCommentDraft={(value) => setCommentDrafts((current) => ({ ...current, [post.id]: value }))}
            onPredict={onPredict}
            onSharePost={() => onSharePost(post)}
            onToggleComments={() => onToggleComments(post.id)}
            onComment={() => onComment(post.id)}
          />
        ))
      )}
    </ScrollView>
  );
}

function PostScreen({
  draft,
  setDraft,
  onSubmit,
  submitting,
  notice
}: {
  draft: FormDraft;
  setDraft: Dispatch<SetStateAction<FormDraft>>;
  onSubmit: () => void;
  submitting: boolean;
  notice: string | null;
}) {
  const update = (key: keyof FormDraft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  return (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <View style={styles.composePanel}>
        <View style={styles.sectionHeader}>
          <Target size={20} color={colors.green} />
          <Text style={styles.sectionTitle}>New setup</Text>
        </View>
        <Field label="Symbol" value={draft.symbol} onChangeText={(value) => update("symbol", value.toUpperCase())} placeholder="SPY" />
        <Text style={styles.fieldLabel}>Direction</Text>
        <View style={styles.segment}>
          <SegmentButton
            active={draft.direction === "long"}
            label="Long"
            icon={<TrendingUp size={16} />}
            onPress={() => setDraft((current) => ({ ...current, direction: "long" }))}
          />
          <SegmentButton
            active={draft.direction === "short"}
            label="Short"
            icon={<TrendingDown size={16} />}
            onPress={() => setDraft((current) => ({ ...current, direction: "short" }))}
          />
        </View>
        <View style={styles.formGrid}>
          <Field
            label="Entry"
            value={draft.entry_price}
            onChangeText={(value) => update("entry_price", value)}
            keyboardType="decimal-pad"
          />
          <Field
            label="Thesis check"
            value={draft.stop_loss}
            onChangeText={(value) => update("stop_loss", value)}
            keyboardType="decimal-pad"
          />
          <Field
            label="Target"
            value={draft.take_profit}
            onChangeText={(value) => update("take_profit", value)}
            keyboardType="decimal-pad"
          />
        </View>
        <Field
          label="Reasoning"
          value={draft.reasoning}
          onChangeText={(value) => update("reasoning", value)}
          placeholder="Key levels, catalyst, thesis check"
          multiline
          inputStyle={styles.textArea}
        />
        <Pressable style={styles.primaryButton} onPress={onSubmit} disabled={submitting}>
          {submitting ? <ActivityIndicator color={colors.bg} /> : <Send size={18} color={colors.bg} />}
          <Text style={styles.primaryButtonText}>Publish setup</Text>
        </Pressable>
        {notice ? <Notice message={notice} /> : null}
      </View>
    </ScrollView>
  );
}

function AccountScreen({
  trader,
  stats,
  wsStatus,
  onRefresh,
  onSignOut,
  refreshing,
  notice
}: {
  trader: Trader;
  stats: { open: number; resolved: number; tp: number; sl: number };
  wsStatus: WsStatus;
  onRefresh: () => void;
  onSignOut: () => void;
  refreshing: boolean;
  notice: string | null;
}) {
  const accuracy = trader.total_predictions
    ? Math.round((trader.correct_predictions / trader.total_predictions) * 100)
    : 0;

  return (
    <ScrollView
      contentContainerStyle={styles.scrollContent}
      refreshControl={<RefreshControl tintColor={colors.green} refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View style={styles.profilePanel}>
        <View style={styles.avatar}>
          <User size={32} color={colors.green} />
        </View>
        <View style={styles.profileCopy}>
          <Text style={styles.profileName}>{trader.username}</Text>
          <Text style={styles.profileMeta}>Trust level {trader.trust_level}</Text>
        </View>
        <View style={styles.goldBadge}>
          <CircleDollarSign size={15} color={colors.amber} />
          <Text style={styles.goldBadgeText}>{trader.gold}</Text>
        </View>
      </View>

      <View style={styles.scoreRow}>
        <MetricTile label="Accuracy" value={`${accuracy}%`} accent={colors.green} icon={<Check size={17} />} />
        <MetricTile label="Calls" value={String(trader.total_predictions)} accent={colors.blue} icon={<Activity size={17} />} />
        <MetricTile label="Open" value={String(stats.open)} accent={colors.amber} icon={<Clock size={17} />} />
      </View>

      <View style={styles.detailPanel}>
        <DetailRow label="Correct predictions" value={String(trader.correct_predictions)} />
        <DetailRow label="Resolved setups" value={String(stats.resolved)} />
        <DetailRow label="TP predictions" value={String(stats.tp)} />
        <DetailRow label="Thesis-check predictions" value={String(stats.sl)} />
        <DetailRow label="API" value={API_URL} />
        <DetailRow label="Feed" value={wsStatus === "connected" ? "connected" : "disconnected"} />
      </View>

      {notice ? <Notice message={notice} /> : null}

      <View style={styles.accountActions}>
        <Pressable style={styles.secondaryButton} onPress={onRefresh}>
          <RefreshCcw size={17} color={colors.text} />
          <Text style={styles.secondaryButtonText}>Refresh</Text>
        </Pressable>
        <Pressable style={styles.dangerButton} onPress={onSignOut}>
          <X size={17} color={colors.red} />
          <Text style={styles.dangerButtonText}>Clear identity</Text>
        </Pressable>
      </View>

      <DisclaimerCard />
    </ScrollView>
  );
}

function TradeCard({
  post,
  expanded,
  comments,
  commentDraft,
  setCommentDraft,
  onPredict,
  onSharePost,
  onToggleComments,
  onComment
}: {
  post: TradePost;
  expanded: boolean;
  comments: Comment[];
  commentDraft: string;
  setCommentDraft: (value: string) => void;
  onPredict: (postId: string, outcome: PredictionOutcome) => void;
  onSharePost: () => void;
  onToggleComments: () => void;
  onComment: () => void;
}) {
  const isLong = post.direction === "long";
  const accent = isLong ? colors.green : colors.red;
  const predictionStats = post.prediction_stats || { tp_predictions: 0, sl_predictions: 0 };
  const settled = post.resolved && post.outcome;

  return (
    <View style={styles.postCard}>
      <View style={styles.postTop}>
        <View style={styles.symbolBlock}>
          <Text style={styles.symbolText}>{post.symbol}</Text>
          <View style={[styles.directionPill, { backgroundColor: isLong ? colors.greenSoft : colors.redSoft }]}>
            {isLong ? <TrendingUp size={14} color={colors.green} /> : <TrendingDown size={14} color={colors.red} />}
            <Text style={[styles.directionText, { color: accent }]}>{post.direction.toUpperCase()}</Text>
          </View>
        </View>
        <View style={styles.authorBlock}>
          <Text style={styles.authorText} numberOfLines={1}>{post.user.username}</Text>
          <GoldChip amount={post.user.gold} compact />
        </View>
      </View>

      <View style={styles.levels}>
        <Level label="Entry" value={formatPrice(post.entry_price)} />
        <Level label="Thesis check" value={formatPrice(post.stop_loss)} />
        <Level label="Target" value={formatPrice(post.take_profit)} />
      </View>

      <View style={styles.contextRow}>
        <Text style={styles.contextText}>Model {formatPercent(post.foxtrot_score)}</Text>
        <Text style={styles.contextText}>{post.regime || "regime n/a"}</Text>
        <Text style={styles.contextText}>Conf {formatPercent(post.confidence)}</Text>
      </View>

      {post.reasoning ? <Text style={styles.reasoningText}>{post.reasoning}</Text> : null}

      <View style={styles.predictionBar}>
        <View style={styles.predictionSide}>
          <Target size={14} color={colors.green} />
          <Text style={styles.predictionText}>TP {predictionStats.tp_predictions}</Text>
        </View>
        <View style={styles.predictionSide}>
          <ShieldCheck size={14} color={colors.red} />
          <Text style={styles.predictionText}>Check {predictionStats.sl_predictions}</Text>
        </View>
        <Text style={styles.ageText}>{formatAge(post.created_at)}</Text>
      </View>

      {settled ? (
        <View style={styles.settledBand}>
          <Check size={16} color={colors.bg} />
          <Text style={styles.settledText}>{String(post.outcome).replace("_", " ").toUpperCase()}</Text>
        </View>
      ) : post.user_prediction ? (
        <View style={styles.userPrediction}>
          <Check size={15} color={colors.green} />
          <Text style={styles.userPredictionText}>You picked {post.user_prediction.replace("_", " ").toUpperCase()}</Text>
        </View>
      ) : (
        <View style={styles.actionRow}>
          <Pressable style={styles.actionButton} onPress={() => onPredict(post.id, "tp_hit")}>
            <TrendingUp size={16} color={colors.green} />
            <Text style={styles.actionButtonText}>TP hit</Text>
          </Pressable>
          <Pressable style={styles.actionButton} onPress={() => onPredict(post.id, "sl_hit")}>
            <TrendingDown size={16} color={colors.red} />
            <Text style={styles.actionButtonText}>Check hit</Text>
          </Pressable>
        </View>
      )}

      <View style={styles.postUtilityRow}>
        <Pressable style={styles.commentToggle} onPress={onToggleComments}>
          <MessageCircle size={16} color={colors.blue} />
          <Text style={styles.commentToggleText}>Comments</Text>
          <ChevronDown size={16} color={colors.dim} style={expanded ? styles.chevronOpen : undefined} />
        </Pressable>
        <Pressable style={styles.shareToggle} onPress={onSharePost} accessibilityLabel="Share setup link">
          <Share2 size={16} color={colors.green} />
          <Text style={styles.shareToggleText}>Share</Text>
        </Pressable>
      </View>

      {expanded ? (
        <View style={styles.commentsPane}>
          {comments.length === 0 ? <Text style={styles.emptyCommentText}>No comments yet.</Text> : null}
          {comments.map((comment) => (
            <View key={comment.id} style={styles.commentRow}>
              <Text style={styles.commentAuthor}>{comment.user.username}</Text>
              <Text style={styles.commentBody}>{comment.content}</Text>
            </View>
          ))}
          <View style={styles.commentComposer}>
            <TextInput
              value={commentDraft}
              onChangeText={setCommentDraft}
              placeholder="Reply"
              placeholderTextColor={colors.dim}
              style={styles.commentInput}
            />
            <Pressable style={styles.iconButton} onPress={onComment}>
              <Send size={16} color={colors.bg} />
            </Pressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}

function Field({
  label,
  containerStyle,
  inputStyle,
  ...props
}: ComponentProps<typeof TextInput> & {
  label: string;
  containerStyle?: object;
  inputStyle?: object;
}) {
  return (
    <View style={[styles.fieldWrap, containerStyle]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        placeholderTextColor={colors.dim}
        style={[styles.input, inputStyle]}
        {...props}
      />
    </View>
  );
}

function MetricTile({ label, value, accent, icon }: { label: string; value: string; accent: string; icon: IconElement }) {
  return (
    <View style={styles.metricTile}>
      <View style={styles.metricIcon}>{withIconColor(icon, accent)}</View>
      <Text style={styles.metricValue} numberOfLines={1}>{value}</Text>
      <Text style={styles.metricLabel} numberOfLines={1}>{label}</Text>
    </View>
  );
}

function AssetChip({ asset, active, onPress }: { asset: AssetPreset; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[styles.assetChip, active ? styles.assetChipActive : null]} onPress={onPress}>
      <Text style={[styles.assetChipSymbol, active ? styles.assetChipSymbolActive : null]}>{asset.symbol}</Text>
      <Text style={styles.assetChipLabel} numberOfLines={1}>{asset.category}</Text>
    </Pressable>
  );
}

function SegmentButton({ active, label, icon, onPress }: { active: boolean; label: string; icon: IconElement; onPress: () => void }) {
  return (
    <Pressable style={[styles.segmentButton, active ? styles.segmentButtonActive : null]} onPress={onPress}>
      {withIconColor(icon, active ? colors.bg : colors.muted)}
      <Text style={[styles.segmentText, active ? styles.segmentTextActive : null]}>{label}</Text>
    </Pressable>
  );
}

function TabButton({ active, label, icon, onPress }: { active: boolean; label: string; icon: IconElement; onPress: () => void }) {
  return (
    <Pressable style={[styles.tabButton, active ? styles.tabButtonActive : null]} onPress={onPress}>
      {withIconColor(icon, active ? colors.green : colors.dim)}
      <Text style={[styles.tabText, active ? styles.tabTextActive : null]}>{label}</Text>
    </Pressable>
  );
}

function ContextLine({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <View style={styles.contextLine}>
      <View style={styles.contextLineTop}>
        <Text style={styles.contextLineLabel}>{label}</Text>
        <Text style={styles.contextLineValue}>{value}</Text>
      </View>
      <Text style={styles.contextLineNote}>{note}</Text>
    </View>
  );
}

function Level({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.level}>
      <Text style={styles.levelLabel}>{label}</Text>
      <Text style={styles.levelValue}>{value}</Text>
    </View>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

function ChanceMeter({ up, down }: { up: number; down: number }) {
  const upPct = Math.round(up * 100);
  const downPct = Math.round(down * 100);
  return (
    <View style={styles.chanceWrap}>
      <View style={styles.chanceLabels}>
        <Text style={styles.chanceLabel}>Up {upPct}%</Text>
        <Text style={styles.chanceLabel}>Down {downPct}%</Text>
      </View>
      <View style={styles.chanceTrack}>
        <View style={[styles.chanceUp, { flex: Math.max(1, upPct) }]} />
        <View style={[styles.chanceDown, { flex: Math.max(1, downPct) }]} />
      </View>
    </View>
  );
}

function IndicatorRow({
  label,
  value,
  note,
  accent
}: {
  label: string;
  value: string;
  note: string;
  accent: string;
}) {
  return (
    <View style={styles.indicatorRow}>
      <View style={[styles.indicatorDot, { backgroundColor: accent }]} />
      <View style={styles.indicatorCopy}>
        <Text style={styles.indicatorLabel}>{label}</Text>
        <Text style={styles.indicatorNote}>{note}</Text>
      </View>
      <Text style={styles.indicatorValue}>{value}</Text>
    </View>
  );
}

function Notice({ message }: { message: string }) {
  return (
    <View style={styles.notice}>
      <Text style={styles.noticeText}>{message}</Text>
    </View>
  );
}

function EmptyState() {
  return (
    <View style={styles.emptyState}>
      <Activity size={28} color={colors.blue} />
      <Text style={styles.emptyTitle}>No setups on the tape.</Text>
    </View>
  );
}

function buildMarketRead(
  symbol: string,
  posts: TradePost[],
  currentPrice: number | null,
  positionSide: PositionSide,
  positionEntry: number | null,
  apiRead: BiasRead | null
) {
  const normalizedSymbol = symbol.trim().toUpperCase() || "SPY";
  const selectedAsset = assetPresetFor(normalizedSymbol);
  if (apiRead) {
    return buildLiveMarketRead(apiRead, selectedAsset, currentPrice, positionSide, positionEntry);
  }

  const matching = posts.find((post) => !post.resolved && post.symbol.toUpperCase() === normalizedSymbol)
    || posts.find((post) => !post.resolved)
    || posts[0];

  if (!matching) {
    return {
      symbol: normalizedSymbol,
      action: "NEUTRAL",
      accent: colors.amber,
      chanceUp: 0.5,
      chanceDown: 0.5,
      why: selectedAsset.why,
      zone: "Wait for a posted range with entry, thesis check, and target.",
      thesisCheck: {
        label: "Thesis check",
        value: "No active thesis check",
        note: "A directional read needs a level where the idea starts to weaken."
      } satisfies ThesisCheck,
      positionTitle: "No active read",
      positionNote: "Add the first setup from the Post tab, then this read will turn into a live triage panel.",
      overhead: buildOverheadRows(selectedAsset, null, null, 0),
      micro: buildMicroRows(selectedAsset, null, currentPrice),
      indicators: [
        { label: "Trend", value: "n/a", note: "No regime context yet", accent: colors.dim },
        { label: "Range", value: "n/a", note: "No entry or thesis check yet", accent: colors.dim },
        { label: "Crowd", value: "0 / 0", note: "No predictions yet", accent: colors.dim }
      ]
    };
  }

  const setupSymbol = matching.symbol.toUpperCase();
  const asset = assetPresetFor(setupSymbol);
  const foxtrot = typeof matching.foxtrot_score === "number" ? clamp(matching.foxtrot_score, 0, 1) : null;
  const confidence = typeof matching.confidence === "number" ? clamp(matching.confidence, 0, 1) : 0.5;
  const chanceUp = foxtrot ?? (matching.direction === "long" ? 0.5 + confidence * 0.35 : 0.5 - confidence * 0.35);
  const chanceDown = 1 - chanceUp;
  const obviousSide: Direction | "neutral" = chanceUp >= 0.56 ? "long" : chanceUp <= 0.44 ? "short" : "neutral";
  const accent = obviousSide === "long" ? colors.green : obviousSide === "short" ? colors.red : colors.amber;
  const action = obviousSide === "long"
    ? "LONG"
    : obviousSide === "short"
      ? "SHORT"
      : "NEUTRAL";
  const split = matching.prediction_stats || { tp_predictions: 0, sl_predictions: 0 };
  const crowdTotal = split.tp_predictions + split.sl_predictions;
  const crowdLean = crowdTotal === 0
    ? "No crowd lean"
    : split.tp_predictions >= split.sl_predictions
      ? "Crowd leans TP"
      : "Crowd leans thesis check";

  const zone = buildZoneText(matching, currentPrice);
  const position = buildPositionNote(matching, currentPrice, positionSide, positionEntry);

  return {
    symbol: setupSymbol,
    action,
    accent,
    chanceUp,
    chanceDown,
    why: `${asset.why} Current read: ${Math.round(chanceUp * 100)}% up / ${Math.round(chanceDown * 100)}% down from the latest desk context.`,
    zone,
    thesisCheck: buildThesisCheck(matching),
    positionTitle: position.title,
    positionNote: position.note,
    overhead: buildOverheadRows(asset, matching, obviousSide, crowdTotal),
    micro: buildMicroRows(asset, matching, currentPrice),
    indicators: [
      {
        label: "Trend",
        value: matching.regime || "n/a",
        note: `Setup direction is ${matching.direction.toUpperCase()}`,
        accent: matching.direction === "long" ? colors.green : colors.red
      },
      {
        label: "Momentum",
        value: formatPercent(foxtrot),
        note: "Model probability context",
        accent
      },
      {
        label: "Range",
        value: `${formatPrice(matching.stop_loss)} / ${formatPrice(matching.take_profit)}`,
        note: `Entry area ${formatPrice(matching.entry_price)}`,
        accent: colors.blue
      },
      {
        label: "Conviction",
        value: formatPercent(confidence),
        note: "Signal agreement from the backend",
        accent: confidence >= 0.6 ? colors.green : confidence <= 0.35 ? colors.red : colors.amber
      },
      {
        label: "Crowd",
        value: `${split.tp_predictions} / ${split.sl_predictions}`,
        note: crowdLean,
        accent: split.tp_predictions >= split.sl_predictions ? colors.green : colors.red
      }
    ]
  };
}

function buildLiveMarketRead(
  apiRead: BiasRead,
  selectedAsset: AssetPreset,
  currentPrice: number | null,
  positionSide: PositionSide,
  positionEntry: number | null
) {
  const symbol = apiRead.symbol.trim().toUpperCase() || selectedAsset.symbol;
  const asset = assetPresetFor(symbol);
  const action = apiRead.bias;
  const accent = accentForBias(action);
  const chanceUp = clamp(apiRead.probability_up ?? 0.5, 0, 1);
  const chanceDown = clamp(apiRead.probability_down ?? (1 - chanceUp), 0, 1);
  const shownPrice = currentPrice ?? apiRead.price ?? null;
  const position = buildLivePositionNote(apiRead, shownPrice, positionSide, positionEntry);
  const sourceHealth = sourceHealthSummary(apiRead.source_health);
  const drivers = apiRead.drivers && apiRead.drivers.length > 0
    ? apiRead.drivers.slice(0, 5).map((driver) => ({
        label: driver.name || "Driver",
        value: driver.impact || driver.lean || "mixed",
        note: driver.plain_english || driver.detail || "Driver context was provided by the API.",
        accent: accentForImpact(driver.impact || driver.lean)
      }))
    : [
        { label: "Trend", value: "n/a", note: "No driver detail returned yet.", accent: colors.dim },
        { label: "Volume", value: "n/a", note: "No volume detail returned yet.", accent: colors.dim }
      ];

  return {
    symbol,
    action,
    accent,
    chanceUp,
    chanceDown,
    why: apiRead.thesis || apiRead.human_readable || asset.why,
    zone: apiRead.invalidation?.reason || "No thesis-check level returned for this read.",
    thesisCheck: buildApiThesisCheck(apiRead),
    positionTitle: position.title,
    positionNote: position.note,
    overhead: [
      {
        label: "Role",
        value: asset.category,
        note: asset.why
      },
      {
        label: "Source health",
        value: sourceHealth.value,
        note: sourceHealth.note
      },
      {
        label: "Regime",
        value: apiRead.regime_hint || "unknown",
        note: "This is the current market environment used by CoinFox."
      }
    ],
    micro: [
      {
        label: "Price now",
        value: shownPrice === null ? "Not entered" : formatPrice(shownPrice),
        note: shownPrice === null ? "Enter live price for local triage." : "Compared against the live API read."
      },
      {
        label: "24h change",
        value: typeof apiRead.change_24h_pct === "number" ? `${apiRead.change_24h_pct.toFixed(2)}%` : "n/a",
        note: "Recent movement context from public market data."
      },
      {
        label: "Updated",
        value: formatTimestamp(apiRead.timestamp || apiRead.updated_at),
        note: "Refresh if this read looks stale."
      }
    ],
    indicators: drivers
  };
}

function assetPresetFor(symbol: string): AssetPreset {
  const normalized = symbol.trim().toUpperCase();
  return MAJOR_ASSETS.find((asset) => asset.symbol === normalized) || {
    symbol: normalized || "CUSTOM",
    label: normalized || "Custom",
    category: "Custom",
    why: "Custom market. Keep it watchable, but anchor the read to price, range, liquidity, and correlated majors.",
    drivers: ["correlated majors", "news tape", "liquidity"],
    details: ["session high/low", "VWAP", "volume impulse"]
  };
}

function buildOverheadRows(
  asset: AssetPreset,
  post: TradePost | null,
  obviousSide: Direction | "neutral" | null,
  crowdTotal: number
) {
  const direction = obviousSide === "long" ? "Risk-on" : obviousSide === "short" ? "Risk-off" : "Mixed";
  const setupText = post
    ? `${post.direction.toUpperCase()} setup in ${post.regime || "unknown"} regime`
    : "No live setup yet";
  return [
    {
      label: "Role",
      value: asset.category,
      note: asset.why
    },
    {
      label: "Macro pulse",
      value: direction,
      note: `Watch ${asset.drivers.join(", ")} before trusting the first move.`
    },
    {
      label: "Desk state",
      value: setupText,
      note: crowdTotal > 0 ? `${crowdTotal} trader predictions are already on the tape.` : "No crowd read yet."
    }
  ];
}

function buildMicroRows(asset: AssetPreset, post: TradePost | null, currentPrice: number | null) {
  const rangeText = post
    ? `${formatPrice(post.stop_loss)} / ${formatPrice(post.entry_price)} / ${formatPrice(post.take_profit)}`
    : "Need posted range";
  const priceText = currentPrice === null ? "Not entered" : formatPrice(currentPrice);
  return [
    {
      label: "Price now",
      value: priceText,
      note: currentPrice === null ? "Enter live price for immediate buy/sell-zone triage." : "Compared against the posted entry, thesis check, and target."
    },
    {
      label: "Range",
      value: rangeText,
      note: post ? "Thesis check / entry / target is the working map." : "A clean idea needs a thesis check before it is useful."
    },
    {
      label: "Tape checks",
      value: asset.details.slice(0, 2).join(", "),
      note: asset.details[2] || "Look for confirmation before sizing up."
    }
  ];
}

function buildThesisCheck(post: TradePost): ThesisCheck {
  const operator = post.direction === "long" ? "<=" : ">=";
  const side = post.direction === "long" ? "long" : "short";
  const structure = post.direction === "long" ? "support" : "resistance";
  return {
    label: "Thesis invalid if",
    value: `price ${operator} ${formatPrice(post.stop_loss)}`,
    note: `This ${side} idea weakens if price breaks the ${structure} area.`
  };
}

function buildApiThesisCheck(read: BiasRead): ThesisCheck {
  const invalidation = read.invalidation;
  if (!invalidation || read.bias === "NEUTRAL") {
    return {
      label: "Thesis check",
      value: "No active thesis check",
      note: "CoinFox only shows a thesis-check level when the read has a directional lean."
    };
  }
  const operator = invalidation.type === "price_above" ? ">" : invalidation.type === "price_below" ? "<" : "";
  const value = invalidation.level === null || invalidation.level === undefined
    ? "Level not available"
    : `price ${operator} ${formatPrice(invalidation.level)}`;
  return {
    label: invalidation.not_a_stop_loss ? invalidation.label || "Thesis check" : "Thesis check",
    value,
    note: invalidation.reason
  };
}

function buildLivePositionNote(
  read: BiasRead,
  currentPrice: number | null,
  positionSide: PositionSide,
  positionEntry: number | null
) {
  if (positionSide === "flat") {
    return {
      title: "Flat",
      note: read.invalidation?.reason || read.thesis || "Watch for a cleaner thesis check before acting."
    };
  }
  if (currentPrice === null || positionEntry === null) {
    return {
      title: `${positionSide.toUpperCase()} active`,
      note: "Add current price and your entry to compare your position with the live read."
    };
  }

  const pnl = positionSide === "long"
    ? (currentPrice - positionEntry) / positionEntry
    : (positionEntry - currentPrice) / positionEntry;
  const aligned = biasToPositionSide(read.bias) === positionSide;
  return {
    title: `${formatSignedPct(pnl)} vs entry`,
    note: aligned
      ? "Your side matches the live read. Keep checking the thesis level and source health."
      : `You are ${positionSide.toUpperCase()} while CoinFox reads ${read.bias}. Re-check the thesis before adding risk.`
  };
}

function buildZoneText(post: TradePost, currentPrice: number | null): string {
  const entry = post.entry_price;
  const stop = post.stop_loss;
  const target = post.take_profit;
  if (currentPrice === null) {
    return `${post.direction === "long" ? "Buy" : "Sell"} area ${formatPrice(entry)}; thesis check ${formatPrice(stop)}; target ${formatPrice(target)}.`;
  }

  const nearEntry = Math.abs(currentPrice - entry) / entry <= 0.005;
  if (post.direction === "long") {
    if (currentPrice <= stop) return "Below thesis check. This is no longer the same long idea.";
    if (nearEntry) return "At the potential buy area. The thesis check defines the no-go line.";
    if (currentPrice < entry) return "Below entry. Watch for a reclaim before chasing.";
    if (currentPrice >= target) return "At or beyond target. Fresh entries need a new range.";
    return "Between entry and target. Manage risk instead of pretending it is still early.";
  }

  if (currentPrice >= stop) return "Above thesis check. This is no longer the same short idea.";
  if (nearEntry) return "At the potential sell area. The thesis check defines the no-go line.";
  if (currentPrice > entry) return "Above entry. Watch for rejection before chasing.";
  if (currentPrice <= target) return "At or beyond target. Fresh shorts need a new range.";
  return "Between entry and target. Manage risk instead of pretending it is still early.";
}

function buildPositionNote(
  post: TradePost,
  currentPrice: number | null,
  positionSide: PositionSide,
  positionEntry: number | null
) {
  if (positionSide === "flat") {
    return {
      title: "Flat",
      note: buildZoneText(post, currentPrice)
    };
  }
  if (currentPrice === null || positionEntry === null) {
    return {
      title: `${positionSide.toUpperCase()} active`,
      note: "Add current price and your entry to get live triage against this setup."
    };
  }

  const pnl = positionSide === "long"
    ? (currentPrice - positionEntry) / positionEntry
    : (positionEntry - currentPrice) / positionEntry;
  const aligned = positionSide === post.direction;
  const invalidated = positionSide === "long" ? currentPrice <= post.stop_loss : currentPrice >= post.stop_loss;
  const atTarget = positionSide === "long" ? currentPrice >= post.take_profit : currentPrice <= post.take_profit;

  if (invalidated) {
    return {
      title: `${formatSignedPct(pnl)} vs entry`,
      note: "Price is through the thesis check. Treat hope as expensive here."
    };
  }
  if (atTarget) {
    return {
      title: `${formatSignedPct(pnl)} vs entry`,
      note: "Price is at the target zone. Protect the win or wait for a fresh setup."
    };
  }
  if (!aligned) {
    return {
      title: `${formatSignedPct(pnl)} vs entry`,
      note: `You are ${positionSide.toUpperCase()} while the desk setup is ${post.direction.toUpperCase()}. Keep the exit plan close.`
    };
  }
  if (pnl > 0) {
    return {
      title: `${formatSignedPct(pnl)} vs entry`,
      note: "Trade is working. The question is now thesis protection, not prediction."
    };
  }
  return {
    title: `${formatSignedPct(pnl)} vs entry`,
    note: "Trade is not working yet. The thesis check is the line that keeps an idea from becoming a story."
  };
}

function parseDraft(draft: FormDraft): TradePostDraft | null {
  const entry = Number(draft.entry_price);
  const stop = Number(draft.stop_loss);
  const target = Number(draft.take_profit);
  if (!Number.isFinite(entry) || !Number.isFinite(stop) || !Number.isFinite(target)) return null;
  if (entry <= 0 || stop <= 0 || target <= 0) return null;
  return {
    symbol: draft.symbol.trim().toUpperCase() || "SPY",
    direction: draft.direction,
    entry_price: entry,
    stop_loss: stop,
    take_profit: target,
    reasoning: draft.reasoning.trim() || undefined
  };
}

function formatPrice(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return value >= 1000 ? value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : value.toFixed(2);
}

function parseOptionalNumber(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function createAnonymousId(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function accentForBias(bias: BiasDirection): string {
  if (bias === "LONG") return colors.green;
  if (bias === "SHORT") return colors.red;
  return colors.amber;
}

function accentForImpact(impact?: string): string {
  const clean = String(impact || "").toLowerCase();
  if (clean.includes("bull") || clean.includes("long")) return colors.green;
  if (clean.includes("bear") || clean.includes("short")) return colors.red;
  return colors.amber;
}

function biasToPositionSide(bias: BiasDirection): PositionSide {
  if (bias === "LONG") return "long";
  if (bias === "SHORT") return "short";
  return "flat";
}

function sourceHealthSummary(sourceHealth?: BiasRead["source_health"]) {
  if (!sourceHealth) {
    return { value: "unknown", note: "No source-health detail returned yet." };
  }
  if (typeof sourceHealth === "string") {
    return { value: sourceHealth, note: "Source health was returned as a simple status." };
  }
  const stale = sourceHealth.stale_sources || [];
  const notes = sourceHealth.notes || [];
  return {
    value: sourceHealth.status || "unknown",
    note: notes[0] || (stale.length ? `Stale sources: ${stale.join(", ")}` : "Sources recently returned usable data.")
  };
}

function formatTimestamp(value?: string): string {
  if (!value) return "n/a";
  const ts = new Date(value).getTime();
  if (!Number.isFinite(ts)) return "n/a";
  return formatAge(value);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function formatSignedPct(value: number): string {
  if (!Number.isFinite(value)) return "0.0%";
  const pct = value * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function formatAge(iso: string): string {
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return "";
  const diff = Math.max(0, Date.now() - ts);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

function withIconColor(icon: IconElement, color: string) {
  return cloneElement(icon, { color });
}

const styles = StyleSheet.create({
  app: {
    flex: 1,
    backgroundColor: colors.bg
  },
  keyboard: {
    flex: 1
  },
  header: {
    paddingHorizontal: 18,
    paddingTop: 12,
    paddingBottom: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  },
  kicker: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  title: {
    color: colors.text,
    fontSize: 26,
    fontWeight: "800",
    letterSpacing: 0,
    marginTop: 2
  },
  connectionPill: {
    height: 32,
    paddingHorizontal: 10,
    borderRadius: radii.sm,
    borderWidth: 1,
    flexDirection: "row",
    gap: 6,
    alignItems: "center"
  },
  connected: {
    borderColor: colors.green,
    backgroundColor: colors.greenSoft
  },
  disconnected: {
    borderColor: colors.red,
    backgroundColor: colors.redSoft
  },
  connectionText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  content: {
    flex: 1
  },
  centerPane: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  scrollContent: {
    padding: 14,
    paddingBottom: 110,
    gap: 12
  },
  readControls: {
    flexDirection: "row",
    gap: 10
  },
  readControlField: {
    flex: 1
  },
  assetRail: {
    gap: 8,
    paddingRight: 18
  },
  assetChip: {
    width: 88,
    minHeight: 52,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panel,
    paddingHorizontal: 10,
    paddingVertical: 8,
    justifyContent: "center",
    gap: 3
  },
  assetChipActive: {
    borderColor: colors.green,
    backgroundColor: colors.greenSoft
  },
  assetChipSymbol: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0
  },
  assetChipSymbolActive: {
    color: colors.green
  },
  assetChipLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "800"
  },
  readPanel: {
    backgroundColor: colors.panel,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 12,
    ...shadow
  },
  readHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12
  },
  readHeaderActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  iconGhostButton: {
    width: 34,
    height: 34,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.panelAlt,
    alignItems: "center",
    justifyContent: "center"
  },
  readLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  readAction: {
    fontSize: 30,
    fontWeight: "900",
    letterSpacing: 0,
    marginTop: 2
  },
  readBadge: {
    minHeight: 34,
    minWidth: 64,
    borderRadius: radii.sm,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 10,
    backgroundColor: colors.bg
  },
  readBadgeText: {
    fontSize: 14,
    fontWeight: "900"
  },
  readWhy: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 21,
    fontWeight: "700"
  },
  chanceWrap: {
    gap: 8
  },
  chanceLabels: {
    flexDirection: "row",
    justifyContent: "space-between"
  },
  chanceLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "900"
  },
  chanceTrack: {
    height: 12,
    borderRadius: 6,
    overflow: "hidden",
    flexDirection: "row",
    backgroundColor: colors.border
  },
  chanceUp: {
    backgroundColor: colors.green
  },
  chanceDown: {
    backgroundColor: colors.red
  },
  zoneBand: {
    minHeight: 44,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.panelAlt,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    gap: 8
  },
  zoneText: {
    flex: 1,
    color: colors.text,
    fontSize: 13,
    fontWeight: "800",
    lineHeight: 18
  },
  thesisCheckRow: {
    minHeight: 50,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 10,
    paddingVertical: 8
  },
  thesisCheckCopy: {
    flex: 1,
    gap: 2
  },
  thesisCheckLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "900",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  thesisCheckValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  infoButton: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center"
  },
  infoButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  thesisHelp: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 17
  },
  liveStateRow: {
    minHeight: 34,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panelAlt,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 10
  },
  liveStateText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800"
  },
  feedbackRow: {
    flexDirection: "row",
    gap: 8
  },
  feedbackButton: {
    minHeight: 36,
    flex: 1,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.panelAlt,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6
  },
  feedbackButtonText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "900"
  },
  sectionPanel: {
    backgroundColor: colors.panel,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 12,
    ...shadow
  },
  contextLine: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 10,
    gap: 4
  },
  contextLineTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10
  },
  contextLineLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "900",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  contextLineValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900",
    maxWidth: "56%",
    textAlign: "right"
  },
  contextLineNote: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 18
  },
  indicatorRow: {
    minHeight: 52,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  indicatorDot: {
    width: 10,
    height: 10,
    borderRadius: 5
  },
  indicatorCopy: {
    flex: 1,
    gap: 2
  },
  indicatorLabel: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  indicatorNote: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  indicatorValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900",
    maxWidth: 92,
    textAlign: "right"
  },
  assistBox: {
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.amber,
    backgroundColor: colors.amberSoft,
    padding: 10,
    gap: 4
  },
  assistTitle: {
    color: colors.amber,
    fontSize: 16,
    fontWeight: "900"
  },
  assistText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 18
  },
  scoreRow: {
    flexDirection: "row",
    gap: 8
  },
  metricTile: {
    flex: 1,
    minHeight: 88,
    backgroundColor: colors.panel,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 10,
    justifyContent: "space-between",
    ...shadow
  },
  metricIcon: {
    height: 22,
    alignItems: "flex-start",
    justifyContent: "center"
  },
  metricValue: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: 0
  },
  metricLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0
  },
  marketStrip: {
    minHeight: 42,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panelAlt,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    gap: 8
  },
  marketStripText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800"
  },
  marketStripMeta: {
    color: colors.muted,
    fontSize: 13,
    flex: 1
  },
  marketLive: {
    color: colors.green,
    fontSize: 12,
    fontWeight: "900"
  },
  postCard: {
    backgroundColor: colors.panel,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    gap: 12,
    ...shadow
  },
  postTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10
  },
  symbolBlock: {
    flex: 1,
    gap: 6
  },
  symbolText: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: 0
  },
  directionPill: {
    alignSelf: "flex-start",
    minHeight: 28,
    borderRadius: radii.sm,
    paddingHorizontal: 9,
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  directionText: {
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0
  },
  authorBlock: {
    alignItems: "flex-end",
    justifyContent: "center",
    maxWidth: "44%"
  },
  authorText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800"
  },
  authorMeta: {
    color: colors.amber,
    fontSize: 12,
    fontWeight: "700",
    marginTop: 3
  },
  goldChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.amber,
    backgroundColor: colors.amberSoft
  },
  goldChipCompact: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginTop: 3
  },
  goldChipText: {
    color: colors.amber,
    fontSize: 12,
    fontWeight: "800"
  },
  levels: {
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
    paddingVertical: 10,
    flexDirection: "row"
  },
  level: {
    flex: 1
  },
  levelLabel: {
    color: colors.dim,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  levelValue: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "900",
    marginTop: 3
  },
  contextRow: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap"
  },
  contextText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700"
  },
  reasoningText: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20
  },
  predictionBar: {
    minHeight: 34,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  predictionSide: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  predictionText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "800"
  },
  ageText: {
    color: colors.dim,
    fontSize: 12,
    marginLeft: "auto"
  },
  actionRow: {
    flexDirection: "row",
    gap: 8
  },
  actionButton: {
    flex: 1,
    minHeight: 42,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    backgroundColor: colors.panelAlt
  },
  actionButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  settledBand: {
    minHeight: 38,
    borderRadius: radii.sm,
    backgroundColor: colors.green,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7
  },
  settledText: {
    color: colors.bg,
    fontSize: 13,
    fontWeight: "900"
  },
  userPrediction: {
    minHeight: 38,
    borderRadius: radii.sm,
    backgroundColor: colors.greenSoft,
    borderWidth: 1,
    borderColor: colors.green,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7
  },
  userPredictionText: {
    color: colors.green,
    fontSize: 13,
    fontWeight: "900"
  },
  postUtilityRow: {
    minHeight: 36,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  commentToggle: {
    minHeight: 36,
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  commentToggleText: {
    color: colors.blue,
    fontSize: 13,
    fontWeight: "800",
    flex: 1
  },
  shareToggle: {
    minHeight: 36,
    minWidth: 88,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.panelAlt,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingHorizontal: 10
  },
  shareToggleText: {
    color: colors.green,
    fontSize: 13,
    fontWeight: "900"
  },
  chevronOpen: {
    transform: [{ rotate: "180deg" }]
  },
  commentsPane: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: 8,
    gap: 8
  },
  emptyCommentText: {
    color: colors.dim,
    fontSize: 13
  },
  commentRow: {
    gap: 2
  },
  commentAuthor: {
    color: colors.blue,
    fontSize: 12,
    fontWeight: "900"
  },
  commentBody: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 18
  },
  commentComposer: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center"
  },
  commentInput: {
    flex: 1,
    minHeight: 40,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
    color: colors.text,
    paddingHorizontal: 10
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: radii.sm,
    backgroundColor: colors.green,
    alignItems: "center",
    justifyContent: "center"
  },
  composePanel: {
    backgroundColor: colors.panel,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
    gap: 12,
    ...shadow
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "900"
  },
  fieldWrap: {
    gap: 6
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0
  },
  input: {
    minHeight: 46,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
    color: colors.text,
    paddingHorizontal: 12,
    fontSize: 15,
    fontWeight: "700"
  },
  textArea: {
    minHeight: 92,
    paddingTop: 12,
    textAlignVertical: "top"
  },
  segment: {
    minHeight: 44,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 3,
    flexDirection: "row",
    gap: 3,
    backgroundColor: colors.bg
  },
  segmentButton: {
    flex: 1,
    borderRadius: radii.sm,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 6
  },
  segmentButtonActive: {
    backgroundColor: colors.green
  },
  segmentText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: "900"
  },
  segmentTextActive: {
    color: colors.bg
  },
  formGrid: {
    gap: 10
  },
  primaryButton: {
    minHeight: 48,
    borderRadius: radii.sm,
    backgroundColor: colors.green,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  primaryButtonText: {
    color: colors.bg,
    fontSize: 15,
    fontWeight: "900"
  },
  secondaryButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    backgroundColor: colors.panelAlt
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900"
  },
  dangerButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.red,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    backgroundColor: colors.redSoft
  },
  dangerButtonText: {
    color: colors.red,
    fontSize: 14,
    fontWeight: "900"
  },
  notice: {
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.amber,
    backgroundColor: colors.amberSoft,
    padding: 10
  },
  noticeText: {
    color: colors.amber,
    fontSize: 13,
    fontWeight: "800"
  },
  handleRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 10
  },
  handleField: {
    flex: 1
  },
  diceButton: {
    width: 48,
    height: 48,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.panelAlt,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2
  },
  anonNote: {
    color: colors.dim,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 10
  },
  disclaimerBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 18,
    paddingVertical: 6,
    backgroundColor: colors.panel,
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  },
  disclaimerBarText: {
    flex: 1,
    color: colors.dim,
    fontSize: 11,
    fontWeight: "700"
  },
  disclaimerCard: {
    marginTop: 14,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.amber,
    backgroundColor: colors.amberSoft,
    padding: 12,
    gap: 6
  },
  disclaimerCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  disclaimerCardTitle: {
    color: colors.amber,
    fontSize: 13,
    fontWeight: "800"
  },
  disclaimerCardText: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17
  },
  emptyState: {
    minHeight: 160,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panel,
    alignItems: "center",
    justifyContent: "center",
    gap: 10
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900"
  },
  profilePanel: {
    minHeight: 86,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panel,
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    ...shadow
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: radii.md,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  profileCopy: {
    flex: 1
  },
  profileName: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "900"
  },
  profileMeta: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    marginTop: 3
  },
  goldBadge: {
    minHeight: 34,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.amber,
    backgroundColor: colors.amberSoft,
    paddingHorizontal: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  goldBadgeText: {
    color: colors.amber,
    fontSize: 14,
    fontWeight: "900"
  },
  detailPanel: {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panel,
    overflow: "hidden"
  },
  detailRow: {
    minHeight: 44,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  detailLabel: {
    flex: 1,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "800"
  },
  detailValue: {
    maxWidth: "56%",
    color: colors.text,
    fontSize: 13,
    fontWeight: "800",
    textAlign: "right"
  },
  accountActions: {
    flexDirection: "row",
    gap: 8
  },
  accountGate: {
    flex: 1,
    padding: 18,
    justifyContent: "center",
    gap: 14
  },
  gateIcon: {
    width: 64,
    height: 64,
    borderRadius: radii.md,
    backgroundColor: colors.greenSoft,
    alignItems: "center",
    justifyContent: "center"
  },
  gateTitle: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: 0
  },
  tabBar: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    height: 64,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: "#10141A",
    flexDirection: "row",
    padding: 6,
    gap: 4,
    ...shadow
  },
  tabButton: {
    flex: 1,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    gap: 3
  },
  tabButtonActive: {
    backgroundColor: colors.greenSoft
  },
  tabText: {
    color: colors.dim,
    fontSize: 11,
    fontWeight: "900"
  },
  tabTextActive: {
    color: colors.green
  }
});
