import { useEffect, useState } from "react";
import { Card, Row, Col, Statistic, Alert, Typography, Spin } from "antd";
import { Column, Pie } from "@ant-design/plots";
import api, { extractErrorMessage } from "../api/client";
import type { AnalyticsSummary } from "../types";

const { Title, Paragraph } = Typography;

function toChartData(record: Record<string, number>, keyLabel: string, valueLabel = "Count") {
  return Object.entries(record).map(([k, v]) => ({ [keyLabel]: k, [valueLabel]: v }));
}

export default function Analytics() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<{ summary: AnalyticsSummary }>("/analytics/summary", { timeout: 30000 })
      .then((res) => setSummary(res.data.summary))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" tip="Loading analytics (running ML predictions across all customers)..." />
      </div>
    );
  }

  if (error) {
    return <Alert type="error" showIcon message="Could not load analytics" description={error} />;
  }

  if (!summary) return null;

  const atRisk = summary.churn_risk_distribution["At Risk"] ?? 0;
  const stable = summary.churn_risk_distribution["Stable"] ?? 0;
  const totalWithPrediction = atRisk + stable;
  const atRiskPct = totalWithPrediction ? ((atRisk / totalWithPrediction) * 100).toFixed(1) : "0.0";

  // open_tickets / resolved_tickets aren't guaranteed to exist on the
  // backend response yet - fall back to deriving from complaints_by_status
  // if the dedicated fields aren't present.
  const openTickets =
    summary.open_tickets ?? summary.complaints_by_status["Open"] ?? 0;
  const resolvedTickets =
    summary.resolved_tickets ??
    (summary.complaints_by_status["Resolved"] ?? 0) + (summary.complaints_by_status["Closed"] ?? 0);

  return (
    <div>
      <Title level={3}>📊 Analytics</Title>

      {summary.prediction_errors > 0 && (
        <Alert
          type="warning"
          showIcon
          className="mb-4"
          message={`${summary.prediction_errors} prediction(s) failed while computing this summary (e.g. models not yet trained) - counts below may be incomplete.`}
        />
      )}

      <Row gutter={16} className="mb-6">
        <Col span={4}>
          <Card><Statistic title="Total Customers" value={summary.total_customers} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="Total Complaints" value={summary.total_complaints} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="🔴 Open Tickets" value={openTickets} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="🟢 Resolved Tickets" value={resolvedTickets} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="Customers At Risk" value={atRisk} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="At-Risk Rate" value={`${atRiskPct}%`} /></Card>
        </Col>
      </Row>

      <Title level={4}>📋 Complaint Trends</Title>
      <Row gutter={16} className="mb-6">
        <Col span={12}>
          <Card title="Complaints by Category">
            <Column
              data={toChartData(summary.complaints_by_issue_type, "type")}
              xField="type"
              yField="Count"
              height={260}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Complaints by Priority">
            <Pie
              data={toChartData(summary.complaints_by_priority, "priority")}
              angleField="Count"
              colorField="priority"
              height={260}
              label={{ text: "Count", style: { fontWeight: "bold" } }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Complaints by Status" className="mb-6">
        <Column
          data={toChartData(summary.complaints_by_status, "status")}
          xField="status"
          yField="Count"
          colorField="status"
          height={260}
        />
      </Card>

      <Title level={4}>🔮 ML Insights Across All Customers</Title>
      <Row gutter={16} className="mb-6">
        <Col span={12}>
          <Card title="Churn Risk Distribution">
            <Pie
              data={toChartData(summary.churn_risk_distribution, "risk")}
              angleField="Count"
              colorField="risk"
              height={260}
              color={({ risk }: any) => (risk === "At Risk" ? "#d62728" : "#2ca02c")}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Recommended Package Tier Distribution">
            <Column
              data={toChartData(summary.package_tier_distribution, "tier")}
              xField="tier"
              yField="Count"
              colorField="tier"
              height={260}
            />
          </Card>
        </Col>
      </Row>

      <Paragraph type="secondary" className="text-xs">
        Churn risk and package tier predictions are based on rule-derived training labels - treat
        as directional/prototype signals until models are retrained on real outcome data.
      </Paragraph>
    </div>
  );
}
