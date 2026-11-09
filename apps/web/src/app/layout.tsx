import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "LabLens — understand your lab report",
  description:
    "Educational support for understanding laboratory report terms and preparing questions for a clinician.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
