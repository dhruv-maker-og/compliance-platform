import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Tab,
  TabList,
  Text,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  ShieldCheckmarkRegular,
  DocumentSearchRegular,
  ShieldTaskRegular,
  ClipboardTextLtrRegular,
} from "@fluentui/react-icons";

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100vh",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 24px",
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
    boxShadow: tokens.shadow4,
  },
  headerTitle: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  nav: {
    padding: "0 24px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
  },
  content: {
    flex: 1,
    padding: "24px",
    maxWidth: "1400px",
    width: "100%",
    margin: "0 auto",
  },
});

const tabs = [
  { value: "/", label: "Dashboard", icon: <ShieldCheckmarkRegular /> },
  { value: "/evidence", label: "Evidence Collection", icon: <DocumentSearchRegular /> },
  { value: "/policy", label: "Policy Enforcer", icon: <ShieldTaskRegular /> },
  { value: "/reports", label: "Reports", icon: <ClipboardTextLtrRegular /> },
];

export default function Layout() {
  const styles = useStyles();
  const location = useLocation();
  const navigate = useNavigate();

  const currentTab = tabs.find((t) => t.value === location.pathname)?.value ?? "/";

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.headerTitle}>
          <ShieldCheckmarkRegular fontSize={28} />
          <Text size={500} weight="bold">
            ComplianceRewind &amp; Policy Enforcer
          </Text>
        </div>
        <Text size={200}>Continuous Compliance Platform</Text>
      </header>

      <nav className={styles.nav}>
        <TabList
          selectedValue={currentTab}
          onTabSelect={(_, data) => navigate(data.value as string)}
        >
          {tabs.map((tab) => (
            <Tab key={tab.value} value={tab.value} icon={tab.icon}>
              {tab.label}
            </Tab>
          ))}
        </TabList>
      </nav>

      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  );
}
