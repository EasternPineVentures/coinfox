// Curated outbound resources — "everything trading" lives here. Grouped so a
// trader can jump to charting, screeners, macro data, filings, news, etc.
// Keep this list trustworthy and free-to-reach; no affiliate junk.

export type ResourceLink = {
  name: string;
  url: string;
  blurb: string;
};

export type ResourceCategory = {
  title: string;
  caption: string;
  links: ResourceLink[];
};

// Intent-first navigation: people think "I want to DO x", not "I need a screener".
// This maps a plain-English need to the one tool to reach for, and why.
export type ResourceGuideItem = {
  need: string;
  pick: string;
  url: string;
  why: string;
};

export const RESOURCE_GUIDE: ResourceGuideItem[] = [
  {
    need: "Pull up a chart fast",
    pick: "TradingView",
    url: "https://www.tradingview.com/",
    why: "Cleanest charts, every market, draw and set alerts in seconds."
  },
  {
    need: "Find names matching a setup",
    pick: "Finviz Screener",
    url: "https://finviz.com/screener.ashx",
    why: "Filter thousands of stocks by trend, volume, float in one screen."
  },
  {
    need: "Know when the Fed moves",
    pick: "CME FedWatch",
    url: "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
    why: "Live market-implied odds of the next rate decision."
  },
  {
    need: "Check this week's catalysts",
    pick: "TradingEconomics",
    url: "https://tradingeconomics.com/calendar",
    why: "Econ calendar so a data drop never blindsides your trade."
  },
  {
    need: "Read what a company actually reported",
    pick: "SEC EDGAR",
    url: "https://www.sec.gov/cgi-bin/browse-edgar",
    why: "The official filings — numbers straight from the source."
  },
  {
    need: "Gauge crypto leverage & liquidations",
    pick: "Coinglass",
    url: "https://www.coinglass.com/",
    why: "Funding, open interest and liq levels that move crypto fast."
  },
  {
    need: "Feel the crowd's mood",
    pick: "Fear & Greed",
    url: "https://www.cnn.com/markets/fear-and-greed",
    why: "One quick read on whether the market is fearful or greedy."
  }
];

export const RESOURCE_CATEGORIES: ResourceCategory[] = [
  {
    title: "Charts & Analysis",
    caption: "Price action, drawing, indicators",
    links: [
      { name: "TradingView", url: "https://www.tradingview.com/", blurb: "Charts, ideas, alerts" },
      { name: "Finviz", url: "https://finviz.com/", blurb: "Maps, heatmaps, quick charts" },
      { name: "Stockcharts", url: "https://stockcharts.com/", blurb: "Classic technical charting" }
    ]
  },
  {
    title: "Screeners",
    caption: "Find names that fit a setup",
    links: [
      { name: "Finviz Screener", url: "https://finviz.com/screener.ashx", blurb: "Fast equity screening" },
      { name: "TradingView Screener", url: "https://www.tradingview.com/screener/", blurb: "Stocks & crypto filters" },
      { name: "CoinGecko", url: "https://www.coingecko.com/", blurb: "Crypto market screener" }
    ]
  },
  {
    title: "Data & Macro",
    caption: "The backdrop behind every move",
    links: [
      { name: "FRED", url: "https://fred.stlouisfed.org/", blurb: "Fed economic data" },
      { name: "CME FedWatch", url: "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html", blurb: "Rate-hike odds" },
      { name: "TradingEconomics", url: "https://tradingeconomics.com/calendar", blurb: "Global econ calendar" }
    ]
  },
  {
    title: "Filings & Fundamentals",
    caption: "What companies actually report",
    links: [
      { name: "SEC EDGAR", url: "https://www.sec.gov/cgi-bin/browse-edgar", blurb: "Official filings (10-K/Q, 8-K)" },
      { name: "Macrotrends", url: "https://www.macrotrends.net/", blurb: "Long-term fundamentals" }
    ]
  },
  {
    title: "News & Sentiment",
    caption: "Catalysts and the crowd",
    links: [
      { name: "Reuters Markets", url: "https://www.reuters.com/markets/", blurb: "Wire-grade market news" },
      { name: "Fear & Greed", url: "https://www.cnn.com/markets/fear-and-greed", blurb: "Market sentiment gauge" }
    ]
  },
  {
    title: "Crypto",
    caption: "On-chain and derivatives",
    links: [
      { name: "Coinglass", url: "https://www.coinglass.com/", blurb: "Funding, OI, liquidations" },
      { name: "DefiLlama", url: "https://defillama.com/", blurb: "TVL & protocol data" },
      { name: "Etherscan", url: "https://etherscan.io/", blurb: "Ethereum explorer" }
    ]
  }
];
