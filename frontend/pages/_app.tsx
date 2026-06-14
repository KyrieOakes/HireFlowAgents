// ================================================================
// Next.js App 入口 — 全局样式 + Layout 包裹
// ================================================================

import type { AppProps } from "next/app";
import Layout from "@/components/Layout";
import "@/styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <Layout>
      <Component {...pageProps} />
    </Layout>
  );
}
