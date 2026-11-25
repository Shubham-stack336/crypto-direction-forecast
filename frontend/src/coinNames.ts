const NAMES: Record<string, string> = {
  BTC: "Bitcoin", ETH: "Ethereum", SOL: "Solana", DOGE: "Dogecoin", XRP: "XRP", BNB: "BNB", ADA: "Cardano",
  AVAX: "Avalanche", LINK: "Chainlink", DOT: "Polkadot", LTC: "Litecoin", TRX: "TRON", SHIB: "Shiba Inu",
  SUI: "Sui", DASH: "Dash", ZEC: "Zcash", NEAR: "NEAR Protocol", UNI: "Uniswap", PEPE: "Pepe", BCH: "Bitcoin Cash",
};

export const coinName = (base: string) => NAMES[base] ?? "USDT pair";
