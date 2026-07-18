import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ChatPage from './pages/ChatPage'
import HomePage from './pages/HomePage'
import SettingsPage from './pages/SettingsPage'
import UsagePage from './pages/UsagePage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/chats/:chatId" element={<ChatPage />} />
          <Route path="/projects/:projectId/usage" element={<UsagePage />} />
          <Route path="/usage" element={<UsagePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
