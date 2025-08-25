import React, { useState, useEffect } from 'react';
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

import { Switch } from "@/components/ui/switch";
import {
    FileText,
    Download,
    Plus,
    BarChart3,
    Users,
    BookOpen,
    GraduationCap,
    TrendingUp,
    Settings,
    RefreshCw,
    AlertCircle,
    CheckCircle,
    XCircle,
    Brain,
    Clock,
    Filter,
} from 'lucide-react';
// import { toast } from 'sonner';
import { reportsService } from '@/services/reportsService';

// Types
interface Report {
    id: number;
    title: string;
    description?: string;
    report_type: string;
    status: 'pending' | 'generating' | 'completed' | 'failed' | 'expired';
    format: 'pdf' | 'excel' | 'csv' | 'json';
    requested_date: string;
    generated_date?: string;
    file_name?: string;
    file_size?: number;
    access_count: number;
    is_public: boolean;
}

interface ReportTemplate {
    id: number;
    name: string;
    description?: string;
    report_type: string;
    is_active: boolean;
    is_default: boolean;
    created_date: string;
}

interface ReportAnalytics {
    total_reports: number;
    reports_by_type: Record<string, number>;
    reports_by_status: Record<string, number>;
    reports_by_format: Record<string, number>;
    success_rate: number;
    storage_used: number;
}

const Reports: React.FC = () => {
    const [reports, setReports] = useState<Report[]>([]);
    const [templates, setTemplates] = useState<ReportTemplate[]>([]);
    const [analytics, setAnalytics] = useState<ReportAnalytics | null>(null);
    const [loading, setLoading] = useState(true);
    const [filterType, setFilterType] = useState<string>('all');
    const [filterStatus, setFilterStatus] = useState<string>('all');
    const [isGenerateDialogOpen, setIsGenerateDialogOpen] = useState(false);
    const [isTemplateDialogOpen, setIsTemplateDialogOpen] = useState(false);
    const fileInputRef = React.useRef<HTMLInputElement | null>(null);
    const [extracting, setExtracting] = useState(false);

    // Report generation form state
    const [generateForm, setGenerateForm] = useState({
        title: '',
        report_type: '',
        template_id: '',
        subject_id: '',
        classroom_id: '',
        student_id: '',
        date_from: '',
        date_to: '',
        format: 'pdf',
        include_charts: true,
        include_summary: true,
        enhanceWithAI: true,
    });

    // Template creation form state
    const [templateForm, setTemplateForm] = useState({
        name: '',
        description: '',
        report_type: '',
        template_config: '{}',
        is_default: false,
    });

    const reportTypes = [
        { value: 'student_progress', label: 'Student Progress', icon: <GraduationCap className="w-4 h-4" /> },
        { value: 'class_performance', label: 'Class Performance', icon: <Users className="w-4 h-4" /> },
        { value: 'subject_analytics', label: 'Subject Analytics', icon: <BookOpen className="w-4 h-4" /> },
        { value: 'assignment_analysis', label: 'Assignment Analysis', icon: <FileText className="w-4 h-4" /> },
        { value: 'grade_distribution', label: 'Grade Distribution', icon: <BarChart3 className="w-4 h-4" /> },
        { value: 'teacher_performance', label: 'Teacher Performance', icon: <TrendingUp className="w-4 h-4" /> },
    ];

    const statusColors = {
        pending: 'bg-yellow-100 text-yellow-800',
        generating: 'bg-blue-100 text-blue-800',
        completed: 'bg-green-100 text-green-800',
        failed: 'bg-red-100 text-red-800',
        expired: 'bg-gray-100 text-gray-800',
    };

    const statusIcons = {
        pending: <Clock className="w-3 h-3" />,
        generating: <RefreshCw className="w-3 h-3 animate-spin" />,
        completed: <CheckCircle className="w-3 h-3" />,
        failed: <XCircle className="w-3 h-3" />,
        expired: <AlertCircle className="w-3 h-3" />,
    };

    useEffect(() => {
        fetchReports();
        fetchTemplates();
        fetchAnalytics();
    }, []);

    const fetchReports = async () => {
        try {
            const schoolId = parseInt(localStorage.getItem('school_id') || '0');
            const data = await reportsService.getReports(schoolId);
            setReports(data);
        } catch (error) {
            console.error('Error fetching reports:', error);
            console.error('Error fetching reports');
        } finally {
            setLoading(false);
        }
    };

    const fetchTemplates = async () => {
        try {
            const schoolId = parseInt(localStorage.getItem('school_id') || '0');
            const data = await reportsService.getReportTemplates(schoolId);
            setTemplates(data);
        } catch (error) {
            console.error('Error fetching templates:', error);
        }
    };

    const fetchAnalytics = async () => {
        try {
            const schoolId = parseInt(localStorage.getItem('school_id') || '0');
            const data = await reportsService.getReportAnalytics(schoolId);
            setAnalytics(data);
        } catch (error) {
            console.error('Error fetching analytics:', error);
        }
    };

    const generateReport = async () => {
        try {
            const schoolId = parseInt(localStorage.getItem('school_id') || '0');

            const requestData = {
                ...generateForm,
                school_id: schoolId,
                template_id: generateForm.template_id ? parseInt(generateForm.template_id) : undefined,
                subject_id: generateForm.subject_id ? parseInt(generateForm.subject_id) : undefined,
                classroom_id: generateForm.classroom_id ? parseInt(generateForm.classroom_id) : undefined,
                student_id: generateForm.student_id ? parseInt(generateForm.student_id) : undefined,
                date_from: generateForm.date_from ? new Date(generateForm.date_from).toISOString() : undefined,
                date_to: generateForm.date_to ? new Date(generateForm.date_to).toISOString() : undefined,
            };

            if (generateForm.enhanceWithAI) {
                await reportsService.generateEnhancedReport(requestData);
                console.log('Enhanced report generation started with K.A.N.A. AI insights');
            } else {
                await reportsService.generateReport(requestData);
                console.log('Report generation started');
            }

            setIsGenerateDialogOpen(false);
            setGenerateForm({
                title: '',
                report_type: '',
                template_id: '',
                subject_id: '',
                classroom_id: '',
                student_id: '',
                date_from: '',
                date_to: '',
                format: 'pdf',
                include_charts: true,
                include_summary: true,
                enhanceWithAI: true,
            });
            fetchReports();
        } catch (error) {
            console.error('Error generating report:', error);
            console.error('Error generating report');
        }
    };

    const downloadReport = async (reportId: number) => {
        try {
            await reportsService.downloadReport(reportId);
            console.log('Report downloaded');
        } catch (error) {
            console.error('Error downloading report:', error);
            console.error('Error downloading report');
        }
    };

    const deleteReport = async (reportId: number) => {
        try {
            await reportsService.deleteReport(reportId);
            console.log('Report deleted');
            fetchReports();
        } catch (error) {
            console.error('Error deleting report:', error);
            console.error('Error deleting report');
        }
    };

    const createTemplate = async () => {
        try {
            const schoolId = parseInt(localStorage.getItem('school_id') || '0');

            await reportsService.createReportTemplate({
                ...templateForm,
                school_id: schoolId,
            });

            console.log('Template created');
            setIsTemplateDialogOpen(false);
            setTemplateForm({
                name: '',
                description: '',
                report_type: '',
                template_config: '{}',
                is_default: false,
            });
            fetchTemplates();
        } catch (error) {
            console.error('Error creating template:', error);
            console.error('Error creating template');
        }
    };

    const filteredReports = reports.filter(report => {
        if (filterType !== 'all' && report.report_type !== filterType) return false;
        if (filterStatus !== 'all' && report.status !== filterStatus) return false;
        return true;
    });

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatReportType = (type: string) => {
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <RefreshCw className="w-8 h-8 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Reports</h1>
                    <p className="text-muted-foreground">
                        Generate and manage comprehensive academic reports
                    </p>
                </div>
                <div className="flex gap-2">
                    <Dialog open={isTemplateDialogOpen} onOpenChange={setIsTemplateDialogOpen}>
                        <DialogTrigger asChild>
                            <Button variant="outline">
                                <Settings className="w-4 h-4 mr-2" />
                                Templates
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>Create Report Template</DialogTitle>
                                <DialogDescription>
                                    Create a reusable template for generating reports
                                </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="template-name" className="text-right">
                                        Name
                                    </Label>
                                    <Input
                                        id="template-name"
                                        value={templateForm.name}
                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTemplateForm(prev => ({ ...prev, name: e.target.value }))}
                                        className="col-span-3"
                                    />
                                </div>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="template-type" className="text-right">
                                        Type
                                    </Label>
                                    <Select
                                        value={templateForm.report_type}
                                        onValueChange={(value: string) => setTemplateForm(prev => ({ ...prev, report_type: value }))}
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".png,.jpg,.jpeg,.bmp,.tiff,.webp,.pdf"
                                        className="hidden"
                                        onChange={async (e) => {
                                            const f = e.target.files?.[0];
                                            if (!f) return;
                                            try {
                                                setExtracting(true);
                                                const data = await reportsService.extractReportCard(f);
                                                console.log('Extracted report card JSON:', data);
                                                // TODO: display nicely or store as needed
                                            } catch (err) {
                                                console.error('Failed to extract report card:', err);
                                            } finally {
                                                setExtracting(false);
                                                e.currentTarget.value = '';
                                            }
                                        }}
                                    />
                                    <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={extracting}>
                                        {extracting ? 'Extracting…' : 'Upload Report Card'}
                                    </Button>
                                    <SelectTrigger className="col-span-3">
                                        <SelectValue placeholder="Select report type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {reportTypes.map((type) => (
                                            <SelectItem key={type.value} value={type.value}>
                                                <div className="flex items-center gap-2">
                                                    {type.icon}
                                                    {type.label}
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="template-description" className="text-right">
                                    Description
                                </Label>
                                <Textarea
                                    id="template-description"
                                    value={templateForm.description}
                                    onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setTemplateForm(prev => ({ ...prev, description: e.target.value }))}
                                    className="col-span-3"
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button onClick={createTemplate}>Create Template</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                <Dialog open={isGenerateDialogOpen} onOpenChange={setIsGenerateDialogOpen}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="w-4 h-4 mr-2" />
                            Generate Report
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Generate New Report</DialogTitle>
                            <DialogDescription>
                                Create a comprehensive report for your school data
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="title" className="text-right">
                                    Title
                                </Label>
                                <Input
                                    id="title"
                                    value={generateForm.title}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGenerateForm(prev => ({ ...prev, title: e.target.value }))}
                                    className="col-span-3"
                                />
                            </div>

                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="report-type" className="text-right">
                                    Type
                                </Label>
                                <Select
                                    value={generateForm.report_type}
                                    onValueChange={(value: string) => setGenerateForm(prev => ({ ...prev, report_type: value }))}
                                >
                                    <SelectTrigger className="col-span-3">
                                        <SelectValue placeholder="Select report type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {reportTypes.map((type) => (
                                            <SelectItem key={type.value} value={type.value}>
                                                <div className="flex items-center gap-2">
                                                    {type.icon}
                                                    {type.label}
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="template" className="text-right">
                                    Template
                                </Label>
                                <Select
                                    value={generateForm.template_id}
                                    onValueChange={(value: string) => setGenerateForm(prev => ({ ...prev, template_id: value }))}
                                >
                                    <SelectTrigger className="col-span-3">
                                        <SelectValue placeholder="Select template (optional)" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {templates.map((template) => (
                                            <SelectItem key={template.id} value={template.id.toString()}>
                                                {template.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="format" className="text-right">
                                    Format
                                </Label>
                                <Select
                                    value={generateForm.format}
                                    onValueChange={(value: string) => setGenerateForm(prev => ({ ...prev, format: value }))}
                                >
                                    <SelectTrigger className="col-span-3">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="pdf">PDF</SelectItem>
                                        <SelectItem value="excel">Excel</SelectItem>
                                        <SelectItem value="csv">CSV</SelectItem>
                                        <SelectItem value="json">JSON</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="date-from" className="text-right">
                                    Date From
                                </Label>
                                <Input
                                    id="date-from"
                                    type="date"
                                    value={generateForm.date_from}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGenerateForm(prev => ({ ...prev, date_from: e.target.value }))}
                                    className="col-span-3"
                                />
                            </div>

                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="date-to" className="text-right">
                                    Date To
                                </Label>
                                <Input
                                    id="date-to"
                                    type="date"
                                    value={generateForm.date_to}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGenerateForm(prev => ({ ...prev, date_to: e.target.value }))}
                                    className="col-span-3"
                                />
                            </div>

                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="ai-enhance" className="text-right">
                                    <div className="flex items-center gap-2">
                                        <Brain className="w-4 h-4" />
                                        K.A.N.A. AI
                                    </div>
                                </Label>
                                <div className="col-span-3 flex items-center gap-2">
                                    <Switch
                                        id="ai-enhance"
                                        checked={generateForm.enhanceWithAI}
                                        onCheckedChange={(checked: boolean) => setGenerateForm(prev => ({ ...prev, enhanceWithAI: checked }))}
                                    />
                                    <span className="text-sm text-muted-foreground">
                                        Enhance with AI insights and recommendations
                                    </span>
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button onClick={generateReport}>Generate Report</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>

            {/* Analytics Cards */ }
    {
        analytics && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Reports</CardTitle>
                        <FileText className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{analytics.total_reports}</div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
                        <TrendingUp className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{analytics.success_rate.toFixed(1)}%</div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
                        <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{formatBytes(analytics.storage_used)}</div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Active Templates</CardTitle>
                        <Settings className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{templates.filter(t => t.is_active).length}</div>
                    </CardContent>
                </Card>
            </div>
        )
    }

    {/* Filters */ }
    <Card>
        <CardHeader>
            <CardTitle className="flex items-center gap-2">
                <Filter className="w-5 h-5" />
                Filters
            </CardTitle>
        </CardHeader>
        <CardContent>
            <div className="flex gap-4">
                <div className="flex-1">
                    <Label htmlFor="filter-type">Report Type</Label>
                    <Select value={filterType} onValueChange={setFilterType}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Types</SelectItem>
                            {reportTypes.map((type) => (
                                <SelectItem key={type.value} value={type.value}>
                                    {type.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <div className="flex-1">
                    <Label htmlFor="filter-status">Status</Label>
                    <Select value={filterStatus} onValueChange={setFilterStatus}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Status</SelectItem>
                            <SelectItem value="pending">Pending</SelectItem>
                            <SelectItem value="generating">Generating</SelectItem>
                            <SelectItem value="completed">Completed</SelectItem>
                            <SelectItem value="failed">Failed</SelectItem>
                            <SelectItem value="expired">Expired</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </CardContent>
    </Card>

    {/* Reports Table */ }
    <Card>
        <CardHeader>
            <CardTitle className="flex items-center justify-between">
                <span>Reports ({filteredReports.length})</span>
                <Button variant="outline" size="sm" onClick={fetchReports}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                </Button>
            </CardTitle>
        </CardHeader>
        <CardContent>
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Title</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Format</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Size</TableHead>
                        <TableHead>Actions</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {filteredReports.map((report) => (
                        <TableRow key={report.id}>
                            <TableCell className="font-medium">{report.title}</TableCell>
                            <TableCell>{formatReportType(report.report_type)}</TableCell>
                            <TableCell>
                                <Badge className={statusColors[report.status]}>
                                    <div className="flex items-center gap-1">
                                        {statusIcons[report.status]}
                                        {report.status}
                                    </div>
                                </Badge>
                            </TableCell>
                            <TableCell className="uppercase">{report.format}</TableCell>
                            <TableCell>
                                {new Date(report.requested_date).toLocaleDateString()}
                            </TableCell>
                            <TableCell>
                                {report.file_size ? formatBytes(report.file_size) : '-'}
                            </TableCell>
                            <TableCell>
                                <div className="flex gap-2">
                                    {report.status === 'completed' && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => downloadReport(report.id)}
                                        >
                                            <Download className="w-4 h-4" />
                                        </Button>
                                    )}
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => deleteReport(report.id)}
                                    >
                                        <XCircle className="w-4 h-4" />
                                    </Button>
                                </div>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>

            {filteredReports.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                    No reports found. Generate your first report to get started.
                </div>
            )}
        </CardContent>
    </Card>
        </div >
    );
};

export { Reports };
