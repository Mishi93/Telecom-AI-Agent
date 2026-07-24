export interface Customer {
  customer_id: string;
  name: string;
}

export interface ChatHistoryTurn {
  role: "user" | "assistant";
  content: string;
}
