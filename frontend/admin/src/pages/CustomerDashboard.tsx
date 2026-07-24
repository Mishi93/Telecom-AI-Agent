import { useEffect, useState } from "react";
import { Select, Card, Statistic, Row, Col, Table, Empty, Alert, Divider, Typography, Spin } from "antd";
import { Column } from "@ant-design/plots";
import api, { extractErrorMessage } from "../api/client";
import type { Customer, CustomerDetail, Complaint, ChurnPrediction, PackagePrediction } from "../types";

const { Title, Text, Paragraph } = Typography;

export default function CustomerDashboard() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<string | undefined>();

  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [complaints, setComplaints] = useState<Complaint[] | null>(null);
  const [complaintsError, setComplaintsError] = useState<string | null>(null);

  const [churn, setChurn] = useState<ChurnPrediction | null>(null);
  const [churnError, setChurnError] = useState<string | null>(null);

  const [pkg, setPkg] = useState<PackagePrediction | null>(null);
  const [pkgError, setPkgError] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get<Customer[]>("/customers")
      .then((res) => setCustomers(res.data))
      .catch(() => setCustomers([]));
  }, []);

  useEffect(() => {
    if (!customerId) return;

    setLoading(true);
    setDetail(null);
    setDetailError(null);
    setComplaints(null);
    setComplaintsError(null);
    setChurn(null);
    setChurnError(null);
    setPkg(null);
    setPkgError(null);

    api
      .get<CustomerDetail>(`/customers/${customerId}`)
      .then((res) => setDetail(res.data))
      .catch((err) => setDetailError(extractErrorMessage(err)));

    api
      .get<Complaint[]>(`/customers/${customerId}/complaints`)
      .then((res) => setComplaints(res.data))
      .catch((err) => setComplaintsError(extractErrorMessage(err)));

    api
      .get<{ prediction: ChurnPrediction }>(`/predict/churn/${customerId}`)
      .then((res) => setChurn(res.data.prediction))
      .catch((err) => setChurnError(extractErrorMessage(err)))
      .finally(() => setLoading(false));

    api
      .get<{ prediction: PackagePrediction }>(`/predict/package/${customerId}`)
      .then((res) => setPkg(res.data.prediction))
      .catch((err) => setPkgError(extractErrorMessage(err)));
  }, [customerId]);

  const complaintColumns = [
    { title: "Ticket ID", dataIndex: "ticket_id", key: "ticket_id" },
    { title: "Issue Type", dataIndex: "issue_type", key: "issue_type" },
    { title: "Priority", dataIndex: "priority", key: "priority" },
    { title: "Status", dataIndex: "status", key: "status" },
    { title: "Description", dataIndex: "description", key: "description" },
    {
      title: "Created At",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string | null) => (v ? new Date(v).toLocaleString() : "—"),
    },
  ];

  const tierChartData = pkg
    ? Object.entries(pkg.tier_probabilities).map(([tier, probability]) => ({ tier, probability }))
    : [];

  return (
    <div>
      <Title level={3}>👤 Customer Dashboard</Title>

      <Select
        showSearch
        placeholder="Select Customer"
        className="w-full max-w-md mb-6"
        value={customerId}
        onChange={setCustomerId}
        options={customers.map((c) => ({
          value: c.customer_id,
          label: `${c.customer_id} (${c.name})`,
        }))}
        filterOption={(input, option) =>
          (option?.label as string).toLowerCase().includes(input.toLowerCase())
        }
      />

      {!customerId && (
        <Empty description="Select or enter a customer ID above to view their dashboard." />
      )}

      {customerId && (
        <Spin spinning={loading}>
          {detailError && <Alert type="error" showIcon message={detailError} className="mb-4" />}
          {detail && (
            <>
              <Title level={4}>
                Profile: {detail.name} ({detail.customer_id})
              </Title>
              <Row gutter={16} className="mb-6">
                <Col span={8}>
                  <Card>
                    <Statistic title="Balance" prefix="$" value={detail.balance.toFixed(2)} />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card>
                    <Statistic title="Data Remaining" value={detail.data_remaining} />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card>
                    <Statistic title="Minutes Remaining" value={detail.minutes_remaining} />
                  </Card>
                </Col>
              </Row>
            </>
          )}

          <Divider />
          <Title level={4}>📋 Complaint History</Title>
          {complaintsError && <Alert type="error" showIcon message={complaintsError} className="mb-4" />}
          {complaints && complaints.length === 0 && (
            <Empty description="No complaints on file for this customer." />
          )}
          {complaints && complaints.length > 0 && (
            <Table
              rowKey="ticket_id"
              dataSource={complaints}
              columns={complaintColumns}
              pagination={{ pageSize: 5 }}
            />
          )}

          <Divider />
          <Title level={4}>🔮 ML Insights</Title>
          <Row gutter={24}>
            <Col span={12}>
              <Card title="Churn Risk">
                {churnError && <Alert type="warning" showIcon message={churnError} />}
                {churn && (
                  <>
                    <Alert
                      type={churn.churn_risk ? "error" : "success"}
                      showIcon
                      message={
                        churn.churn_risk
                          ? `⚠️ At Risk — ${(churn.churn_probability * 100).toFixed(0)}% probability`
                          : `✅ Stable — ${(churn.churn_probability * 100).toFixed(0)}% churn probability`
                      }
                    />
                    <Paragraph type="secondary" className="mt-2 text-xs">
                      Based on a rule-derived label (2+ open, high-priority complaints) - swap in
                      real churn outcomes for production use.
                    </Paragraph>
                  </>
                )}
              </Card>
            </Col>
            <Col span={12}>
              <Card title="Recommended Plan Tier">
                {pkgError && <Alert type="warning" showIcon message={pkgError} />}
                {pkg && (
                  <>
                    <Alert type="info" showIcon message={`📦 Recommended: ${pkg.recommended_tier}`} className="mb-4" />
                    <Column
                      data={tierChartData}
                      xField="tier"
                      yField="probability"
                      height={200}
                      yAxis={{ min: 0, max: 1 }}
                      label={{ position: "top" }}
                    />
                  </>
                )}
              </Card>
            </Col>
          </Row>
        </Spin>
      )}
    </div>
  );
}
