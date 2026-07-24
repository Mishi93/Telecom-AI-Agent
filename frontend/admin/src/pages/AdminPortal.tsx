import { useEffect, useState } from "react";
import {
  Tabs,
  Form,
  Input,
  InputNumber,
  Button,
  Select,
  Checkbox,
  Upload,
  message,
  Popconfirm,
  Empty,
  Card,
  Space,
  Typography,
} from "antd";
import { UploadOutlined, SyncOutlined } from "@ant-design/icons";
import type { UploadProps } from "antd";
import api, { extractErrorMessage } from "../api/client";
import type { Customer, CustomerDetail } from "../types";

const { Title, Text, Paragraph } = Typography;

function useLiveCustomers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await api.get<Customer[]>("/customers");
      setCustomers(res.data);
    } catch {
      setCustomers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return { customers, loading, refresh };
}

// ==========================================
// TAB 1: REGISTER CUSTOMER
// ==========================================
function RegisterTab({ onCreated }: { onCreated: () => void }) {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const onFinish = async (values: any) => {
    setSubmitting(true);
    try {
      await api.post("/customers", {
        customer_id: values.customer_id.trim(),
        name: values.name.trim(),
        balance: values.balance,
        data_remaining: values.data_remaining.trim(),
        minutes_remaining: values.minutes_remaining,
      });
      message.success(`🎉 Successfully registered ${values.name}!`);
      form.resetFields();
      onCreated();
    } catch (err) {
      message.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="max-w-xl">
      <Title level={4}>Register a New Profile</Title>
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{ balance: 50.0, data_remaining: "15.0 GB", minutes_remaining: 500 }}
      >
        <Form.Item name="customer_id" label="Customer ID" rules={[{ required: true, message: "Customer ID is required" }]}>
          <Input placeholder="CUST-105" />
        </Form.Item>
        <Form.Item name="name" label="Customer Full Name" rules={[{ required: true, message: "Full name is required" }]}>
          <Input placeholder="John Doe" />
        </Form.Item>
        <Form.Item name="balance" label="Opening Balance ($)" rules={[{ required: true }]}>
          <InputNumber min={0} step={1} className="w-full" />
        </Form.Item>
        <Form.Item name="data_remaining" label="Assigned Data Plan" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="minutes_remaining" label="Assigned Call Minutes" rules={[{ required: true }]}>
          <InputNumber min={0} step={10} className="w-full" />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>
          Commit Subscriber to Database
        </Button>
      </Form>
    </Card>
  );
}

// ==========================================
// TAB 2: UPDATE CUSTOMER
// ==========================================
function UpdateTab({ customers, loading, onUpdated }: { customers: Customer[]; loading: boolean; onUpdated: () => void }) {
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleSelect = async (customerId: string) => {
    setSelectedId(customerId);
    try {
      const res = await api.get<CustomerDetail>(`/customers/${customerId}`);
      setDetail(res.data);
      form.setFieldsValue(res.data);
    } catch (err) {
      message.error(extractErrorMessage(err));
    }
  };

  const onFinish = async (values: any) => {
    if (!selectedId) return;
    setSubmitting(true);
    try {
      await api.put(`/customers/${selectedId}`, {
        name: values.name.trim(),
        balance: values.balance,
        data_remaining: values.data_remaining.trim(),
        minutes_remaining: values.minutes_remaining,
      });
      message.success(`🎉 Profile ${selectedId} updated successfully!`);
      onUpdated();
    } catch (err) {
      message.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!loading && customers.length === 0) {
    return <Empty description="No active customers available to modify." />;
  }

  return (
    <Card className="max-w-xl">
      <Title level={4}>Modify an Existing Profile</Title>
      <Select
        showSearch
        loading={loading}
        placeholder="Select Customer to Modify"
        className="w-full mb-4"
        value={selectedId}
        onChange={handleSelect}
        options={customers.map((c) => ({
          value: c.customer_id,
          label: `${c.customer_id} (${c.name})`,
        }))}
        filterOption={(input, option) =>
          (option?.label as string).toLowerCase().includes(input.toLowerCase())
        }
      />

      {detail && (
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="name" label="Update Full Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="balance" label="Update Balance ($)" rules={[{ required: true }]}>
            <InputNumber min={0} step={1} className="w-full" />
          </Form.Item>
          <Form.Item name="data_remaining" label="Update Data Allocation" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="minutes_remaining" label="Update Minutes" rules={[{ required: true }]}>
            <InputNumber min={0} step={10} className="w-full" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            Save Modification Changes
          </Button>
        </Form>
      )}
    </Card>
  );
}

// ==========================================
// TAB 3: DELETE CUSTOMER
// ==========================================
function DeleteTab({ customers, loading, onDeleted }: { customers: Customer[]; loading: boolean; onDeleted: () => void }) {
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const selectedLabel = customers.find((c) => c.customer_id === selectedId);

  const handleDelete = async () => {
    if (!selectedId) return;
    setDeleting(true);
    try {
      await api.delete(`/customers/${selectedId}`);
      message.success(`💥 Account ${selectedId} dropped completely.`);
      setSelectedId(undefined);
      setConfirmChecked(false);
      onDeleted();
    } catch (err) {
      message.error(extractErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  if (!loading && customers.length === 0) {
    return <Empty description="No active customers available to delete." />;
  }

  return (
    <Card className="max-w-xl">
      <Title level={4}>Remove Profile from Infrastructure</Title>
      <Select
        showSearch
        loading={loading}
        placeholder="Select Customer to Permanently Remove"
        className="w-full mb-4"
        value={selectedId}
        onChange={(val) => {
          setSelectedId(val);
          setConfirmChecked(false);
        }}
        options={customers.map((c) => ({
          value: c.customer_id,
          label: `${c.customer_id} (${c.name})`,
        }))}
        filterOption={(input, option) =>
          (option?.label as string).toLowerCase().includes(input.toLowerCase())
        }
      />

      {selectedId && (
        <Space direction="vertical" className="w-full">
          <Paragraph type="danger">
            ⚠️ Warning: Deleting <Text code>{selectedId} ({selectedLabel?.name})</Text> will erase
            their entire account profile permanently from the database.
          </Paragraph>
          <Checkbox checked={confirmChecked} onChange={(e) => setConfirmChecked(e.target.checked)}>
            I confirm that I want to delete this customer account permanently.
          </Checkbox>
          <Popconfirm
            title="This action cannot be undone."
            onConfirm={handleDelete}
            okText="Delete"
            okButtonProps={{ danger: true }}
            disabled={!confirmChecked}
          >
            <Button danger type="primary" block disabled={!confirmChecked} loading={deleting}>
              Execute Hard Delete
            </Button>
          </Popconfirm>
        </Space>
      )}
    </Card>
  );
}

// ==========================================
// TAB 4: KNOWLEDGE BASE (RAG) PIPELINE
// ==========================================
function KnowledgeBaseTab() {
  const [fileList, setFileList] = useState<UploadProps["fileList"]>([]);
  const [uploading, setUploading] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  const handleUpload = async () => {
    if (!fileList || fileList.length === 0) {
      message.warning("Please choose a file before attempting deployment.");
      return;
    }
    const file = fileList[0].originFileObj as File;
    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    try {
      await api.post("/rag/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      message.success(`✅ Saved ${file.name} to pipeline storage!`);
      setFileList([]);
    } catch (err) {
      message.error(extractErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    try {
      await api.post("/rag/reindex");
      message.success("🎉 RAG system successfully synchronized! The support agent can now utilize the new information.");
    } catch (err) {
      message.error(extractErrorMessage(err));
    } finally {
      setReindexing(false);
    }
  };

  return (
    <Card className="max-w-2xl">
      <Title level={4}>📚 Infrastructure Knowledge Base Ingestion</Title>
      <Paragraph>
        Upload official telecommunication files (brochures, data charts, or terms of service) to
        update your customer agent's live memory context.
      </Paragraph>

      <Upload
        beforeUpload={() => false}
        maxCount={1}
        accept=".pdf,.csv"
        fileList={fileList}
        onChange={({ fileList: fl }) => setFileList(fl)}
      >
        <Button icon={<UploadOutlined />}>Choose a PDF or CSV document</Button>
      </Upload>

      <Space className="mt-4">
        <Button type="default" onClick={handleUpload} loading={uploading}>
          Deploy Document to Server
        </Button>
        <Button type="primary" icon={<SyncOutlined />} onClick={handleReindex} loading={reindexing}>
          Rebuild Knowledge Vectors
        </Button>
      </Space>
    </Card>
  );
}

// ==========================================
// MAIN PAGE
// ==========================================
export default function AdminPortal() {
  const { customers, loading, refresh } = useLiveCustomers();

  const items = [
    {
      key: "create",
      label: "➕ Register Customer",
      children: <RegisterTab onCreated={refresh} />,
    },
    {
      key: "update",
      label: "✏️ Update Info",
      children: <UpdateTab customers={customers} loading={loading} onUpdated={refresh} />,
    },
    {
      key: "delete",
      label: "❌ Delete Customer",
      children: <DeleteTab customers={customers} loading={loading} onDeleted={refresh} />,
    },
    {
      key: "rag",
      label: "📚 Knowledge Base",
      children: <KnowledgeBaseTab />,
    },
  ];

  return <Tabs defaultActiveKey="create" items={items} />;
}
