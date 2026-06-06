import { colors, fonts } from "@/styles/global";
import { useRouter } from "expo-router";
import { ChevronLeft } from "lucide-react-native";
import type { ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const EFFECTIVE_DATE = "19 May 2026";
const CONTACT_EMAIL = "privacy@finmate.app";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function P({ children }: { children: ReactNode }) {
  return <Text style={styles.paragraph}>{children}</Text>;
}

function Bullet({ children }: { children: ReactNode }) {
  return (
    <View style={styles.bulletRow}>
      <Text style={styles.bulletDot}>•</Text>
      <Text style={styles.bulletText}>{children}</Text>
    </View>
  );
}

export default function PrivacyPolicyScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Pressable style={styles.backBtn} onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={22} color={colors.primary} strokeWidth={2} />
        </Pressable>
        <Text style={styles.headerTitle}>Privacy Policy</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.effective}>Last updated: {EFFECTIVE_DATE}</Text>

        <P>
          FinMate (&quot;FinMate,&quot; &quot;we,&quot; &quot;us,&quot; or &quot;our&quot;) operates a
          mobile application and related services that help users track Pakistan Stock Exchange
          (PSX) portfolios, view market data, and access portfolio analytics and educational
          insights. This Privacy Policy explains what personal information we collect, how we use
          and protect it, and what choices you have.
        </P>
        <P>
          By creating an account or using FinMate, you agree to this Privacy Policy. If you do not
          agree, please do not use the application.
        </P>

        <Section title="1. Information we collect">
          <Text style={styles.subheading}>Account and identity information</Text>
          <P>When you register and maintain your profile, we collect information you provide, including:</P>
          <Bullet>Full name, email address, and mobile phone number</Bullet>
          <Bullet>Password (stored only in hashed form; we never store plain-text passwords)</Bullet>
          <Bullet>
            Know-your-customer (KYC) details such as CNIC number, date of birth, gender, city,
            province, and postal code
          </Bullet>

          <Text style={styles.subheading}>Financial profile information</Text>
          <P>During onboarding or in your Financial Profile settings, you may provide:</P>
          <Bullet>Investment experience level and risk tolerance</Bullet>
          <Bullet>Investment goals and stated income range</Bullet>
          <P>
            This information helps us tailor dashboards, risk summaries, and educational content to
            your stated preferences. It is not used to execute trades on your behalf.
          </P>

          <Text style={styles.subheading}>Portfolio and usage data</Text>
          <P>When you use portfolio features, we store:</P>
          <Bullet>Stocks you add to your portfolio, share quantities, and average buy prices you enter</Bullet>
          <Bullet>Derived metrics such as total invested, current value, and unrealized profit or loss</Bullet>
          <Bullet>
            In-app actions such as screens viewed, features used, and timestamps of activity
          </Bullet>

          <Text style={styles.subheading}>Communications and alerts</Text>
          <P>If you enable notifications, we may process:</P>
          <Bullet>Alert preferences and delivery channels you configure (for example email or messaging integrations)</Bullet>
          <Bullet>Contact details needed to send alerts you have requested</Bullet>

          <Text style={styles.subheading}>Chatbot interactions</Text>
          <P>
            If you use the in-app assistant, we process the messages you send and responses generated
            to provide that feature, maintain conversation context within a session, and improve
            reliability of the service.
          </P>

          <Text style={styles.subheading}>Technical and device information</Text>
          <P>We automatically collect limited technical data, such as:</P>
          <Bullet>Device type, operating system version, and app version</Bullet>
          <Bullet>IP address and general connection metadata</Bullet>
          <Bullet>Authentication tokens used to keep you signed in securely</Bullet>
          <Bullet>Crash logs and diagnostic information when errors occur</Bullet>
        </Section>

        <Section title="2. Information we do not collect">
          <P>
            FinMate does not link to your bank or brokerage accounts unless a future feature
            explicitly states otherwise and requests separate consent. We do not collect payment
            card details through the current application. We do not request access to your contacts,
            photo library, or precise GPS location for core functionality.
          </P>
        </Section>

        <Section title="3. How we use your information">
          <P>We use personal information to:</P>
          <Bullet>Create and secure your account, including verification and password management</Bullet>
          <Bullet>Display and calculate your portfolio performance using prices and data you rely on in the app</Bullet>
          <Bullet>Provide market data, signals, news summaries, and analytics shown in the dashboard</Bullet>
          <Bullet>Send alerts and notifications you have opted into</Bullet>
          <Bullet>Operate the chatbot and related AI-assisted features</Bullet>
          <Bullet>Detect abuse, fraud, and unauthorized access attempts</Bullet>
          <Bullet>Maintain, debug, and improve application performance and security</Bullet>
          <Bullet>Comply with applicable laws and respond to lawful requests from authorities</Bullet>
          <P>
            We do not sell your personal information to third parties for their independent marketing
            purposes.
          </P>
        </Section>

        <Section title="4. Legal bases for processing">
          <P>Depending on applicable law, we process your data because:</P>
          <Bullet>
            <Text style={styles.boldInline}>Contract: </Text>
            Processing is necessary to provide the services you signed up for
          </Bullet>
          <Bullet>
            <Text style={styles.boldInline}>Consent: </Text>
            Where you have given clear consent, such as optional notifications or certain profile fields
          </Bullet>
          <Bullet>
            <Text style={styles.boldInline}>Legitimate interests: </Text>
            To secure our platform, prevent misuse, and improve features in ways that do not override your rights
          </Bullet>
          <Bullet>
            <Text style={styles.boldInline}>Legal obligation: </Text>
            When we must retain or disclose information to meet regulatory or legal requirements
          </Bullet>
        </Section>

        <Section title="5. Market data and automated analysis">
          <P>
            FinMate displays PSX-related prices, technical indicators, forecasts, sentiment scores,
            and portfolio analytics that may be generated or enriched using automated systems,
            including machine-learning models. These outputs are provided for informational and
            educational purposes only. They are not personalized investment advice, a recommendation
            to buy or sell any security, or a guarantee of future performance.
          </P>
          <P>
            Profit and loss figures in your portfolio are calculated from prices and buy prices you
            enter. You are responsible for the accuracy of holdings data you submit.
          </P>
        </Section>

        <Section title="6. How we share information">
          <P>We may share information only in these circumstances:</P>
          <Bullet>
            <Text style={styles.boldInline}>Service providers: </Text>
            Trusted vendors that host our databases, authentication, messaging, analytics, or
            infrastructure (for example cloud hosting, email delivery, or notification gateways).
            They may access data only to perform services for us and under contractual
            confidentiality obligations.
          </Bullet>
          <Bullet>
            <Text style={styles.boldInline}>Professional advisers: </Text>
            Lawyers, auditors, or insurers where reasonably necessary
          </Bullet>
          <Bullet>
            <Text style={styles.boldInline}>Business transfers: </Text>
            If FinMate is involved in a merger, acquisition, or asset sale, user information may
            transfer as part of that transaction subject to this policy or a successor policy
            communicated to you
          </Bullet>
          <Bullet>
            <Text style={styles.boldInline}>Legal and safety: </Text>
            When required by law, court order, or government request, or when we believe disclosure
            is necessary to protect rights, safety, or the integrity of our users and services
          </Bullet>
          <P>We do not share your CNIC or full KYC profile with other users of the application.</P>
        </Section>

        <Section title="7. Data retention">
          <P>
            We keep personal information for as long as your account is active or as needed to
            provide services. If you delete your account or request deletion, we will delete or
            anonymize personal data within a reasonable period, except where we must retain certain
            records for:
          </P>
          <Bullet>Legal, tax, or regulatory compliance</Bullet>
          <Bullet>Resolving disputes or enforcing our terms</Bullet>
          <Bullet>Backup systems that are purged on a regular cycle</Bullet>
          <P>
            Aggregated or de-identified data that cannot reasonably identify you may be retained
            longer for analytics and service improvement.
          </P>
        </Section>

        <Section title="8. Security">
          <P>
            We use administrative, technical, and organizational measures designed to protect your
            information, including:
          </P>
          <Bullet>Encrypted connections (HTTPS/TLS) between the app and our servers</Bullet>
          <Bullet>Hashed storage of passwords and token-based authentication</Bullet>
          <Bullet>Access controls limiting employee and contractor access to production systems</Bullet>
          <Bullet>Monitoring for unusual activity and periodic review of security practices</Bullet>
          <P>
            No method of transmission or electronic storage is completely secure. While we work to
            protect your data, we cannot guarantee absolute security. You are responsible for keeping
            your login credentials confidential and logging out on shared devices.
          </P>
        </Section>

        <Section title="9. Your rights and choices">
          <P>Depending on your location, you may have the right to:</P>
          <Bullet>Access a copy of personal information we hold about you</Bullet>
          <Bullet>Correct inaccurate profile or portfolio data through in-app settings</Bullet>
          <Bullet>Request deletion of your account and associated personal data</Bullet>
          <Bullet>Withdraw consent for optional processing where consent is the legal basis</Bullet>
          <Bullet>Object to or restrict certain processing in limited circumstances</Bullet>
          <Bullet>Receive your data in a portable format where technically feasible</Bullet>
          <P>
            To exercise these rights, contact us at {CONTACT_EMAIL}. We may need to verify your
            identity before fulfilling a request. You can update much of your information directly
            under Profile → Personal Info and Financial Profile.
          </P>
          <P>
            You may opt out of non-essential notifications through Alert Settings or your device
            notification permissions.
          </P>
        </Section>

        <Section title="10. Children">
          <P>
            FinMate is not intended for anyone under 18 years of age. We do not knowingly collect
            personal information from children. If you believe a minor has provided us data, contact
            us at {CONTACT_EMAIL} and we will take steps to delete it.
          </P>
        </Section>

        <Section title="11. International data transfers">
          <P>
            Our infrastructure and service providers may process data in countries other than
            Pakistan, including jurisdictions that may have different data-protection laws. Where
            required, we implement appropriate safeguards for cross-border transfers, such as
            contractual protections with our processors.
          </P>
        </Section>

        <Section title="12. Third-party links and services">
          <P>
            The app may reference external websites, news sources, or market data providers. Those
            third parties operate under their own privacy policies. We are not responsible for their
            practices when you leave FinMate or interact with them outside our application.
          </P>
        </Section>

        <Section title="13. Changes to this policy">
          <P>
            We may update this Privacy Policy from time to time. When we make material changes, we
            will post the revised policy in the app and update the &quot;Last updated&quot; date above.
            Continued use of FinMate after changes take effect constitutes acceptance of the updated
            policy, unless applicable law requires a different form of notice or consent.
          </P>
        </Section>

        <Section title="14. Contact us">
          <P>
            For privacy questions, requests, or complaints, contact:
          </P>
          <Text style={styles.contactLine}>FinMate — Privacy</Text>
          <Text style={styles.contactLine}>Email: {CONTACT_EMAIL}</Text>
          <Text style={styles.contactNote}>
            We aim to respond to verified requests within 30 days. If you are not satisfied with our
            response, you may have the right to lodge a complaint with a data protection authority in
            your jurisdiction.
          </Text>
        </Section>

        <View style={styles.disclaimerBox}>
          <Text style={styles.disclaimerTitle}>Important notice</Text>
          <Text style={styles.disclaimerText}>
            FinMate provides portfolio tracking and market information tools. Investing in securities
            involves risk, including possible loss of principal. Past performance does not guarantee
            future results. Nothing in the app constitutes financial, legal, or tax advice. Consult
            a qualified professional before making investment decisions.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { flex: 1 },
  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
    gap: 4,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
    paddingVertical: 13,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    backgroundColor: colors.background,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontFamily: fonts.heading,
    fontSize: 17,
    color: colors.text,
    letterSpacing: -0.3,
  },

  effective: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    color: colors.mutedText,
    marginBottom: 8,
  },
  section: {
    marginTop: 20,
    gap: 8,
  },
  sectionTitle: {
    fontFamily: fonts.heading,
    fontSize: 16,
    color: colors.text,
    letterSpacing: -0.2,
    marginBottom: 2,
  },
  subheading: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.text,
    marginTop: 6,
  },
  paragraph: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  boldInline: {
    fontFamily: fonts.bodyMedium,
    color: colors.text,
  },
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    paddingLeft: 4,
  },
  bulletDot: {
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.primary,
    lineHeight: 22,
    width: 12,
  },
  bulletText: {
    flex: 1,
    fontFamily: fonts.body,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  contactLine: {
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    color: colors.text,
    lineHeight: 22,
  },
  contactNote: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.mutedText,
    lineHeight: 20,
    marginTop: 4,
  },

  disclaimerBox: {
    marginTop: 28,
    padding: 14,
    borderRadius: 10,
    backgroundColor: colors.bgPrimaryLight,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  disclaimerTitle: {
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    color: colors.primary,
    marginBottom: 6,
  },
  disclaimerText: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
